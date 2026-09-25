"""Book pages for the homework mentor: cached, diagnosable, never raising."""
from __future__ import annotations
import asyncio, base64, io, json, logging, re
from contextlib import closing
from datetime import datetime, timedelta, timezone
from PIL import Image
from .db import webapp_conn
from .secret_store import decrypt_secret
from .textbook_browser import TextbookScanError, capture_pages, looks_blank

_LOGGER=logging.getLogger("schul_cockpit.textbooks")

# Printed pages do not change. The limit only lets a bad capture heal itself.
CACHE_DAYS=30
CACHE_KEEP=60

def page_numbers(text: str, subject: str = "") -> list[int]:
    """Die Schulbuchseiten einer Aufgabe, mit demselben Erkenner wie die
    Quellenbilanz: „p. 50" zählt wie „S. 50", Arbeitsheftseiten bleiben
    draußen, eine Spanne über zehn Seiten ist ein Tippfehler."""
    from .sources import page_hits, wide_spans, part_of, book_serves
    pages=[];wide=wide_spans(text or "")
    for start,_,found in page_hits(text or ""):
        if len(found)>10 or start in wide: continue
        label,kind=part_of(text[:start],subject)
        # Der Begleitband ist ein anderes Buch als das digitale im Regal.
        if kind in ("","book") and book_serves("",label): pages.extend(found)
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


async def fetch_pages(account_id:int,book,credentials,pages:list[int],use_cache:bool=True,survey:bool=False,budget:float=240.0):
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
                                     book["title"],missing,book["launch_url"],survey,budget)
            fresh=seen.shots;detail=seen.note or None
        except TextbookScanError as exc:
            stage=exc.stage;detail=str(exc);seen=getattr(exc,"survey",None)
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


# Ein Aufruf nimmt höchstens so viele Seiten mit: zwei Bilder à zwei Seiten.
SENT_PAGES=4


def _image_parts(shots):
    parts=[]
    blobs=[image for _,image in shots]
    for i in range(0,min(len(blobs),SENT_PAGES),2):
        blob=_join(blobs[i:i+2])
        parts.append({"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(blob).decode(),"detail":"high"}})
    return parts


# Der Chat wartet höchstens so lange auf den Browser (A11). Der Fernzugriff
# kappt eine Anfrage nach 100 Sekunden, und danach kommt noch der Modellaufruf.
# Was bis dahin nicht da ist, holt der Abruf weiter und legt es in den Bestand;
# der nächste Zug hat es ohne Wartezeit.
CHAT_WAIT=45.0
# Das Zeitbudget des Abrufs selbst, der im Hintergrund zu Ende läuft.
FETCH_BUDGET=150.0
# Eine Seite, die nicht zu liefern war, versucht der Chat so lange nicht erneut.
MISS_HOURS=6
BUDGET_NOTE="Zeitbudget erreicht"
# Ein Abruf je Kind und Buch zugleich; ein zweiter Zug wartet auf denselben.
_FETCHES:dict[tuple,tuple]={}  # (Konto, Buch) -> (Task, Seiten)


def _misses(account_id:int,book_id:int,pages:list[int]) -> set[int]:
    if not pages:return set()
    marks=",".join("?"*len(pages))
    try:
        with closing(webapp_conn()) as c:
            return {r[0] for r in c.execute(f"SELECT page FROM digital_textbook_misses WHERE account_id=? AND book_id=? AND until>? AND page IN ({marks})",
                                             (account_id,book_id,_now(),*pages))}
    except Exception:
        return set()


def _remember_misses(account_id:int,book_id:int,pages:list[int],reason:str|None) -> None:
    if not pages:return
    until=(datetime.now(timezone.utc)+timedelta(hours=MISS_HOURS)).isoformat()
    try:
        with closing(webapp_conn()) as c,c:
            c.execute("BEGIN IMMEDIATE")
            for p in pages:
                c.execute("INSERT INTO digital_textbook_misses(account_id,book_id,page,reason,until) VALUES(?,?,?,?,?) "
                          "ON CONFLICT(account_id,book_id,page) DO UPDATE SET reason=excluded.reason,until=excluded.until",
                          (account_id,book_id,p,(reason or "")[:200],until))
    except Exception:
        _LOGGER.warning("Nicht lieferbare Buchseiten für Konto %s nicht vermerkt",account_id)


def forget_misses(account_id:int,book_id:int) -> None:
    """Nach einem erfolgreichen Seitentest der Eltern gilt das Buch wieder als erreichbar."""
    try:
        with closing(webapp_conn()) as c:
            c.execute("DELETE FROM digital_textbook_misses WHERE account_id=? AND book_id=?",(account_id,book_id))
    except Exception:
        _LOGGER.debug("Vermerk nicht lieferbarer Seiten nicht gelöscht",exc_info=True)


async def _fetch_into_stock(account_id:int,book,credentials,subject:str,pages:list[int]) -> dict:
    """Holt die Seiten, legt jede lesbare in den Bestand und vermerkt, was nicht
    zu liefern war. Läuft zu Ende, auch wenn der Chat nicht mehr wartet."""
    from .source_collector import store_page
    result=await fetch_pages(account_id,book,credentials,pages,budget=FETCH_BUDGET)
    got={};blank=[]
    for p,image in result["shots"]:
        if p is None:continue
        if looks_blank(image):blank.append(p);continue
        got[p]=image
        try: store_page(account_id,book,p,image,subject)
        except Exception: _LOGGER.warning("Buchseite %s konnte nicht abgelegt werden",p)
    # Nicht mehr erreicht, weil die Zeit um war, ist kein Fehlschlag (vgl. D112).
    timed_out=(result.get("detail") or "")==BUDGET_NOTE
    failed=[p for p in pages if p not in got and (p in blank or not timed_out)]
    _remember_misses(account_id,book["id"],failed,result.get("stage") or result.get("detail") or result.get("status"))
    return {**result,"got":got}


def _fetch_task(account_id:int,book,credentials,subject:str,pages:list[int]) -> asyncio.Task:
    """Der laufende Abruf für diese Seiten oder ein neuer. Läuft für das Buch
    schon einer mit anderen Seiten, muss der Aufrufer erst dessen Ende abwarten
    (running_for); zwei Browser für dasselbe Buch starten nie."""
    key=(account_id,book["id"])
    running=_FETCHES.get(key)
    if running and not running[0].done():
        return running[0]
    task=asyncio.get_running_loop().create_task(_fetch_into_stock(account_id,book,credentials,subject,pages))
    _FETCHES[key]=(task,set(pages))

    def done(t,key=key):
        if (_FETCHES.get(key) or (None,))[0] is t:_FETCHES.pop(key,None)
        if not t.cancelled() and t.exception():
            _LOGGER.warning("Buchseiten-Abruf für Konto %s gescheitert: %s",key[0],type(t.exception()).__name__)
    task.add_done_callback(done)
    return task


def _running_other(account_id:int,book_id:int,pages:list[int]) -> asyncio.Task|None:
    """Ein laufender Abruf desselben Buchs, der diese Seiten nicht umfasst."""
    running=_FETCHES.get((account_id,book_id))
    if running and not running[0].done() and not set(pages)<=running[1]:
        return running[0]
    return None


async def homework_page_images(account_id:int,subject:str,task_text:str):
    pages=page_numbers(task_text,subject)
    if not pages:return [],{"status":"no_pages"}
    book,credentials=book_and_credentials(account_id,subject=subject)
    if not book or not credentials:return [],{"status":"not_configured","pages":pages}
    # Zuerst der Bestand: Was der Sammellauf schon abgelegt hat, kommt ohne
    # Browser und ohne Wartezeit. Nur der Rest wird jetzt geholt.
    from .source_collector import stored_pages
    kept=stored_pages(account_id,subject,pages)
    missing=[p for p in pages if p not in kept]
    # Was vor Kurzem nicht zu liefern war, startet keinen Browser (A11).
    known_miss=_misses(account_id,book["id"],missing)
    todo=[p for p in missing if p not in known_miss]
    stage=None;detail=None;fallback=[];waiting=False
    if todo:
        loop=asyncio.get_running_loop();deadline=loop.time()+CHAT_WAIT;result=None
        other=_running_other(account_id,book["id"],todo)
        if other is not None:
            # Erst den Abruf anderer Seiten dieses Buchs zu Ende kommen lassen.
            try:
                await asyncio.wait_for(asyncio.shield(other),max(0.0,deadline-loop.time()))
            except asyncio.TimeoutError:
                waiting=True
            kept.update(stored_pages(account_id,subject,todo))
        rest=[p for p in todo if p not in kept]
        if rest and not waiting:
            task=_fetch_task(account_id,book,credentials,subject,rest)
            try:
                result=await asyncio.wait_for(asyncio.shield(task),max(0.0,deadline-loop.time()))
            except asyncio.TimeoutError:
                waiting=True
        if result is not None:
            kept.update({p:image for p,image in result.get("got",{}).items() if p in pages})
            stage=result.get("stage");detail=result.get("detail");fallback=[s for s in result.get("shots",[]) if s[0] is None]
        # Ein zweiter Zug hat womöglich auf einen Abruf anderer Seiten gewartet.
        if any(p not in kept for p in todo):
            kept.update({p:image for p,image in stored_pages(account_id,subject,[p for p in todo if p not in kept]).items()})
    elif known_miss:
        stage="Seitenabruf";detail="Vor Kurzem nicht lieferbar"
    ordered=[(p,kept[p]) for p in pages if p in kept]
    if ordered: status="loaded" if len(ordered)==len(pages) and len(ordered)<=SENT_PAGES else "partial"
    elif fallback: ordered=fallback[:1];status="open_page"
    elif waiting: status="wird_geholt"
    else: status="viewer_error"
    # Gemeldet wird, was wirklich im Aufruf steckt: höchstens SENT_PAGES Seiten.
    shots=ordered[:SENT_PAGES]
    context={"status":status,"book":book["title"],"pages":pages}
    if waiting:
        context["hinweis"]="Die übrigen Buchseiten werden gerade abgerufen und liegen ab der nächsten Nachricht bei."
        stage=stage or "Seitenabruf läuft"
    delivered=[p for p,_ in shots if p is not None]
    if delivered:context["delivered_pages"]=delivered
    # Was gerade noch geholt wird, fehlt nicht: Dafür soll kein Foto verlangt werden.
    pending=[p for p in todo if p not in kept] if waiting else []
    if pending:context["pending_pages"]=pending
    missing=[p for p in pages if p not in delivered and p not in pending]
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
    try:
        from .source_collector import record_access
        if shots and shots[0][0] is not None:
            readable=not looks_blank(shots[0][1])
            record_access(account_id,book["title"],"readable" if readable else "blank",page=page)
            # Die Eltern haben das Buch gerade erreicht: Der Chat darf es wieder versuchen.
            if readable:forget_misses(account_id,book["id"])
        elif delivery["status"]=="viewer_error":
            record_access(account_id,book["title"],"viewer_error",page=page,detail=delivery["detail"])
    except Exception: _LOGGER.warning("Zugriffsnachweis für Konto %s nicht gespeichert",account_id)
    result={"status":delivery["status"],"book":book["title"],"page":page,"stage":delivery["stage"],
            "detail":delivery["detail"],"shown_page":shots[0][0] if shots else None}
    if shots:
        result["image"]="data:image/jpeg;base64,"+base64.b64encode(_jpeg(shots[0][1])).decode()
        try: result["image_size"]=list(Image.open(io.BytesIO(shots[0][1])).size)
        except Exception: result["image_size"]=None
    if seen is not None:
        result["controls"]=seen.controls
        result["documents"]=seen.documents
        result["attempts"]=seen.attempts
        result["entry"]=seen.entry
        result["diagnostics"]=seen.diagnostics
        if seen.window_image:
            result["window_image"]="data:image/jpeg;base64,"+base64.b64encode(_jpeg(seen.window_image)).decode()
    return result


# The parent page test as a background job. A fetch takes 30 seconds to a few
# minutes, and the remote-access proxy in front of Home Assistant cuts every
# request after 100 seconds. So the request starts the job and the page asks
# again until it is done. One job per book at a time; the latest result stays
# until the next one replaces it.
_JOBS:dict[tuple,dict]={}
_JOB_TASKS:dict[tuple,asyncio.Task]={}

def job_state(key:tuple) -> dict:
    return _JOBS.get(key) or {"state":"none"}

async def _run_job(key:tuple,work) -> None:
    try: result=await work()
    except Exception as exc:
        _LOGGER.warning("digital textbook job %s failed: %s",key[1] if len(key)>1 else key,type(exc).__name__)
        result={"status":"viewer_error","stage":"Seitenabruf","detail":type(exc).__name__}
    _JOBS[key]={"state":"done","finished_at":_now(),"result":result}
    _JOB_TASKS.pop(key,None)

def start_job(key:tuple,work,**shown) -> dict:
    """Start the job unless one runs under this key; say what is running."""
    current=_JOBS.get(key)
    if current and current.get("state")=="running": return current
    _JOBS[key]={"state":"running","status":"running","started_at":_now(),**shown}
    _JOB_TASKS[key]=asyncio.get_running_loop().create_task(_run_job(key,work))
    return _JOBS[key]

def page_test_state(account_id:int,book_id:int) -> dict:
    return job_state((account_id,"page-test",book_id))

def start_page_test(account_id:int,book_id:int,page:int) -> dict:
    key=(account_id,"page-test",book_id)
    current=_JOBS.get(key)
    if current and current.get("state")=="running": return current
    book,credentials=book_and_credentials(account_id,book_id=book_id)
    if not book:return {"state":"none","status":"unknown_book"}
    if not credentials:return {"state":"none","status":"not_configured","book":book["title"]}
    async def work():
        try: return await test_page(account_id,book_id,page)
        except Exception as exc:
            _LOGGER.warning("digital textbook page test failed for account %s: %s",account_id,type(exc).__name__)
            return {"status":"viewer_error","page":page,"stage":"Seitenabruf","detail":type(exc).__name__}
    return start_job(key,work,book=book["title"],page=page)

def browser_check_state(account_id:int) -> dict:
    return job_state((account_id,"browser-check"))

def start_browser_check(account_id:int) -> dict:
    """Chromium itself, with and without GPU flags: does WebGL come up, and
    what does the browser say if not? Runs in a thread, minutes at worst."""
    from .textbook_browser import probe_browser
    async def work(): return await asyncio.to_thread(probe_browser)
    return start_job((account_id,"browser-check"),work)
