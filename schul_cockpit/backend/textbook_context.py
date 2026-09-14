"""Book pages for the homework mentor: cached, diagnosable, never raising."""
from __future__ import annotations
import base64, io, json, logging, re
from contextlib import closing
from datetime import datetime, timedelta, timezone
from PIL import Image
from .db import webapp_conn
from .secret_store import decrypt_secret
from .textbook_browser import TextbookScanError, capture_pages

_LOGGER=logging.getLogger("schul_cockpit.textbooks")

# Printed pages do not change. The limit only lets a bad capture heal itself.
CACHE_DAYS=30
CACHE_KEEP=60

def page_numbers(text: str) -> list[int]:
    pages=[]
    for start,end in re.findall(r"(?:S(?:eite)?\.?)\s*(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?",text,re.I):
        a,b=int(start),int(end or start)
        if a<=b<=a+10: pages.extend(range(a,b+1))
    return list(dict.fromkeys(pages))[:6]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _join(blobs):
    images=[Image.open(io.BytesIO(x)).convert("RGB") for x in blobs]
    canvas=Image.new("RGB",(max(x.width for x in images),sum(x.height for x in images)),"white");pos=0
    for image in images: canvas.paste(image,(0,pos));pos+=image.height
    out=io.BytesIO();canvas.save(out,"JPEG",quality=88);return out.getvalue()

def _jpeg(blob: bytes) -> bytes:
    image=Image.open(io.BytesIO(blob)).convert("RGB");image.thumbnail((1400,1400))
    out=io.BytesIO();image.save(out,"JPEG",quality=85);return out.getvalue()

def _cached_pages(account_id:int,book_id:int,pages:list[int]) -> dict[int,bytes]:
    if not pages: return {}
    fresh_since=(datetime.now(timezone.utc)-timedelta(days=CACHE_DAYS)).isoformat()
    marks=",".join("?"*len(pages))
    with closing(webapp_conn()) as c:
        rows=c.execute(f"SELECT page,image FROM digital_textbook_pages WHERE account_id=? AND book_id=? AND captured_at>=? AND page IN ({marks})",
                       (account_id,book_id,fresh_since,*pages)).fetchall()
    return {r["page"]:r["image"] for r in rows}

def _store_pages(account_id:int,book_id:int,shots) -> None:
    keep=[s for s in shots if s.page is not None]
    if not keep: return
    with closing(webapp_conn()) as c,c:
        for shot in keep:
            c.execute("INSERT INTO digital_textbook_pages(account_id,book_id,page,image,captured_at) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(account_id,book_id,page) DO UPDATE SET image=excluded.image,captured_at=excluded.captured_at",
                      (account_id,book_id,shot.page,shot.image,_now()))
        c.execute("DELETE FROM digital_textbook_pages WHERE account_id=? AND rowid NOT IN "
                  "(SELECT rowid FROM digital_textbook_pages WHERE account_id=? ORDER BY captured_at DESC LIMIT ?)",
                  (account_id,account_id,CACHE_KEEP))

def _record(account_id:int,title:str|None,pages:list[int],status:str,stage:str|None,detail:str|None,delivered:int) -> None:
    """Last attempt per child, so the parent view can name the failing step."""
    with closing(webapp_conn()) as c,c:
        c.execute("INSERT INTO digital_textbook_fetches(account_id,book_title,pages,status,stage,detail,delivered,created_at) "
                  "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET book_title=excluded.book_title,"
                  "pages=excluded.pages,status=excluded.status,stage=excluded.stage,detail=excluded.detail,"
                  "delivered=excluded.delivered,created_at=excluded.created_at",
                  (account_id,title,json.dumps(pages),status,stage,detail,delivered,_now()))

def last_fetch(account_id:int) -> dict|None:
    with closing(webapp_conn()) as c:
        row=c.execute("SELECT * FROM digital_textbook_fetches WHERE account_id=?",(account_id,)).fetchone()
    if not row: return None
    result=dict(row)
    try: result["pages"]=json.loads(result["pages"] or "[]")
    except ValueError: result["pages"]=[]
    return result

def book_and_credentials(account_id:int,subject:str|None=None,book_id:int|None=None):
    with closing(webapp_conn()) as c:
        if book_id is not None:
            book=c.execute("SELECT * FROM digital_textbook_catalog WHERE id=? AND account_id=?",(book_id,account_id)).fetchone()
        else:
            book=c.execute("SELECT * FROM digital_textbook_catalog WHERE account_id=? AND lower(subject_name)=lower(?) LIMIT 1",
                           (account_id,subject)).fetchone()
        credentials=c.execute("SELECT * FROM digital_textbook_credentials WHERE account_id=?",(account_id,)).fetchone()
    return book,credentials


async def fetch_pages(account_id:int,book,credentials,pages:list[int],use_cache:bool=True,survey:bool=False):
    """Deliver the requested pages.

    Returns a dict with shots, status, stage, detail and — only when survey is
    set — the viewer diagnostics for the parent view. status is loaded,
    partial, open_page (book open, page unconfirmed) or viewer_error.
    """
    cached=_cached_pages(account_id,book["id"],pages) if use_cache else {}
    missing=[p for p in pages if p not in cached]
    images=dict(cached);fallback=None;stage=None;detail=None;seen=None
    if missing:
        fresh=[];password=""
        try:
            password=decrypt_secret(credentials["password_ciphertext"])
            seen=await capture_pages(credentials["portal_url"],credentials["username"],password,
                                     book["title"],missing,book["launch_url"],survey)
            fresh=seen.shots;detail=seen.note or None
        except TextbookScanError as exc:
            stage=exc.stage;detail=str(exc)
            _LOGGER.warning("digital textbook page fetch failed for account %s in stage %s: %s",
                            account_id,stage or "unbekannt",detail)
        except Exception as exc:
            # Book pages are an addition to the conversation. Whatever breaks
            # here, the mentor keeps working and asks for a photo instead.
            # Only the error class is logged, never keys or page content.
            stage=stage or "Seitenabruf";detail=type(exc).__name__
            _LOGGER.warning("digital textbook page fetch failed for account %s: %s",account_id,detail)
        finally:
            password=""
        for shot in fresh:
            if shot.page is None: fallback=shot.image
            else: images[shot.page]=shot.image
        try: _store_pages(account_id,book["id"],fresh)
        except Exception: _LOGGER.warning("digital textbook page cache write failed for account %s",account_id)
    ordered=[(p,images[p]) for p in pages if p in images]
    if ordered: status="loaded" if len(ordered)==len(pages) else "partial"
    elif fallback: ordered=[(None,fallback)];status="open_page"
    else: status="viewer_error"
    try: _record(account_id,book["title"],pages,status,stage,detail,len(ordered))
    except Exception: _LOGGER.warning("digital textbook fetch log write failed for account %s",account_id)
    return {"shots":ordered,"status":status,"stage":stage,"detail":detail,"seen":seen}


def _image_parts(shots):
    parts=[]
    blobs=[image for _,image in shots]
    for i in range(0,min(len(blobs),4),2):
        blob=_join(blobs[i:i+2])
        parts.append({"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(blob).decode(),"detail":"high"}})
    return parts


async def homework_page_images(account_id:int,subject:str,task_text:str):
    pages=page_numbers(task_text)
    if not pages:return [],{"status":"no_pages"}
    book,credentials=book_and_credentials(account_id,subject=subject)
    if not book or not credentials:return [],{"status":"not_configured","pages":pages}
    result=await fetch_pages(account_id,book,credentials,pages)
    shots=result["shots"];status=result["status"];stage=result["stage"];detail=result["detail"]
    context={"status":status,"book":book["title"],"pages":pages}
    delivered=[p for p,_ in shots if p is not None]
    if delivered:context["delivered_pages"]=delivered
    missing=[p for p in pages if p not in delivered]
    if missing and status!="viewer_error":context["missing_pages"]=missing
    if stage:context["stage"]=stage
    if detail:context["detail"]=detail
    try:
        return _image_parts(shots),context
    except Exception as exc:
        _LOGGER.warning("digital textbook image assembly failed for account %s: %s",account_id,type(exc).__name__)
        return [],{"status":"viewer_error","book":book["title"],"pages":pages,"stage":"Seitenbild aufbereiten"}


async def test_page(account_id:int,book_id:int,page:int) -> dict:
    """Parent-facing single page check; always reports the stage it reached."""
    book,credentials=book_and_credentials(account_id,book_id=book_id)
    if not book:return {"status":"unknown_book"}
    if not credentials:return {"status":"not_configured","book":book["title"]}
    delivery=await fetch_pages(account_id,book,credentials,[page],use_cache=False,survey=True)
    shots=delivery["shots"];seen=delivery["seen"]
    result={"status":delivery["status"],"book":book["title"],"page":page,"stage":delivery["stage"],
            "detail":delivery["detail"],"shown_page":shots[0][0] if shots else None}
    if shots:
        result["image"]="data:image/jpeg;base64,"+base64.b64encode(_jpeg(shots[0][1])).decode()
    if seen is not None:
        result["controls"]=seen.controls
        result["documents"]=seen.documents
        result["attempts"]=seen.attempts
        result["entry"]=seen.entry
        if seen.window_image:
            result["window_image"]="data:image/jpeg;base64,"+base64.b64encode(_jpeg(seen.window_image)).decode()
    return result
