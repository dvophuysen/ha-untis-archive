"""Der Quellenbestand: alles einsammeln, was der Unterricht nennt.

Der Mentor arbeitet am Originalmaterial oder gar nicht. Damit es da ist, bevor
jemand es braucht, holt dieser Dienst die im Unterricht genannten Buchseiten
aus dem Medienregal und legt sie als Materialien ab, mit Herkunft und Seite.
Zwei Läufe am Tag: nach Unterrichtsschluss um 14 Uhr, wenn Hausaufgaben und
Stundeneinträge in Untis stehen, und nachts für alles, was später kam. Der
erste Lauf arbeitet den Bestand seit Schuljahresbeginn ab, danach nur noch
die Differenz.

Eine gelieferte Seite gilt erst, wenn Buchinhalt darauf ist und die gedruckte
Seitenzahl zur Bestellung passt — der Betrachter meldet die Bestellung zurück,
nicht die Lieferung. Was auf Papier existiert, bleibt auf der Einkaufsliste.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from contextlib import closing
from datetime import datetime

from PIL import Image

from . import material_analysis as analysis
from . import sources
from .db import webapp_conn
from .learning import now_iso, today_local
from .textbook_browser import looks_blank
from .textbook_context import book_and_credentials, fetch_pages, job_state, start_job

log = logging.getLogger("schul_cockpit.sources")

AFTERNOON_HOUR = 14
NIGHT_HOUR = 2
# Seiten je Kind und Lauf. Der Erstlauf eines Schuljahresstarts liegt bei
# etwa fünfzig Buchseiten; zwei Läufe, dann ist es die Differenz des Tages.
PAGE_BUDGET = 40
# Nach so vielen vergeblichen Abrufen gilt eine Seite als nicht lieferbar.
MAX_ATTEMPTS = 3
AFTERNOON_KEY = "sources:afternoon"
NIGHT_KEY = "sources:night"


def to_jpeg(blob: bytes, max_side: int = 1600) -> bytes:
    image = Image.open(io.BytesIO(blob)).convert("RGB")
    image.thumbnail((max_side, max_side))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue()


def short_title(title: str) -> str:
    """„BiBox Mathematik Neue Wege 8 Gymnasium G9 Niedersachsen" → „Mathematik Neue Wege 8"."""
    import re
    cut = title.split(" - ")[0].split(" · ")[0].split(":")[0]
    cut = re.sub(r"\b(ab|von)\s+\d{4}\b|\(\d{4}\)|\bG9\b|\bE-Book\b|\bAusgabe\b|\bBiBox\b|\bGymnasium\b|\bNiedersachsen\b|\bBremen\b", " ", cut)
    words = [w for w in cut.split() if w not in (",",)]
    return " ".join(words[:5]).strip(" ,") or title[:60]


def record_access(account_id: int, title: str, status: str, page: int | None = None,
                  printed: int | None = None, detail: str | None = None) -> None:
    """Der Nachweis je Buch: proven schlägt readable, blank und viewer_error
    ersetzen einen Nachweis nicht, solange er einmal gelungen ist."""
    with closing(webapp_conn()) as conn, conn:
        current = conn.execute("SELECT status FROM digital_textbook_access WHERE account_id=? AND book_title=?",
                               (account_id, title)).fetchone()
        rank = {"proven": 3, "readable": 2, "blank": 1, "viewer_error": 1}
        if current and rank.get(current["status"], 0) >= 2 and rank.get(status, 0) < 2:
            conn.execute("UPDATE digital_textbook_access SET detail=?,checked_at=? WHERE account_id=? AND book_title=?",
                         (f"zuletzt {status}" + (f": {detail}" if detail else ""), now_iso(), account_id, title))
            return
        conn.execute(
            "INSERT INTO digital_textbook_access(account_id,book_title,status,page,printed_page,detail,checked_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(account_id,book_title) DO UPDATE SET status=excluded.status,"
            "page=excluded.page,printed_page=excluded.printed_page,detail=excluded.detail,checked_at=excluded.checked_at",
            (account_id, title, status, page, printed, detail, now_iso()))


def access_of(account_id: int, title: str) -> dict | None:
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM digital_textbook_access WHERE account_id=? AND book_title=?",
                           (account_id, title)).fetchone()
    return dict(row) if row else None


def stored_pages(account_id: int, subject: str, pages: list[int]) -> dict[int, bytes]:
    """Abgerufene Buchseiten eines Fachs aus dem Bestand, ohne Browser."""
    if not pages:
        return {}
    marks = ",".join("?" * len(pages))
    with closing(webapp_conn()) as conn:
        rows = conn.execute(
            f"SELECT source_page,file_bytes FROM materials WHERE account_id=? AND origin='book_fetch' AND hidden=0 "
            f"AND lower(subject_name)=lower(?) AND source_page IN ({marks}) "
            f"AND COALESCE(page_check,'')!='mismatch' AND COALESCE(page_check,'')!='blank'",
            (account_id, subject, *pages)).fetchall()
    return {r["source_page"]: r["file_bytes"] for r in rows}


def store_page(account_id: int, book, page: int, image: bytes, subject: str,
               document_date: str | None = None) -> int:
    """Eine gelieferte Buchseite als Material ablegen und zur Auswertung geben.

    Gibt es die Seite schon, wird sie ersetzt und neu ausgewertet: Ein
    zweiter Abruf liefert vielleicht die richtige Seite, wo der erste
    daneben lag.
    """
    jpeg = to_jpeg(image)
    stamp = now_iso()
    title = f"{short_title(book['title'])} S. {page}"
    with closing(webapp_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT id FROM materials WHERE account_id=? AND origin='book_fetch' AND source_book=? AND source_page=?",
            (account_id, book["title"], page)).fetchone()
        if existing:
            conn.execute(
                "UPDATE materials SET file_bytes=?,mime_type='image/jpeg',analysis_state='pending',analysis_error=NULL,"
                "page_check=NULL,printed_pages=NULL,fits_quote=NULL,updated_at=? WHERE id=?",
                (jpeg, stamp, existing["id"]))
            return existing["id"]
        return conn.execute(
            "INSERT INTO materials(account_id,kind,subject_name,title,content_text,document_date,captured_at,"
            "filename,mime_type,file_bytes,page_count,analysis_state,origin,source_book,source_page,created_at,updated_at) "
            "VALUES(?,'book_page',?,?,'',?,?,?,'image/jpeg',?,1,'pending','book_fetch',?,?,?,?)",
            (account_id, subject, title[:200], document_date, stamp, f"buchseite-{page}.jpg", jpeg,
             book["title"], page, stamp, stamp)).lastrowid


def _ai_enabled(account_id: int) -> bool:
    with closing(webapp_conn()) as conn:
        return conn.execute(
            "SELECT 1 FROM learning_profiles WHERE account_id=? AND active=1 AND ai_enabled=1", (account_id,)
        ).fetchone() is not None


async def analyze_page(account_id: int, material_id: int) -> dict | None:
    """Text, Themen und die gedruckte Seitenzahl lesen. Ohne KI bleibt die
    Seite ungeprüft im Bestand und der Nachtlauf holt das nach."""
    if not _ai_enabled(account_id):
        return None
    try:
        await analysis.analyze(account_id, material_id)
    except Exception:
        log.warning("Buchseite %s konnte nicht ausgewertet werden", material_id)
        return None
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT id,page_check,printed_pages,fits_quote,analysis_state FROM materials WHERE id=?",
                           (material_id,)).fetchone()
    return dict(row) if row else None


def _bump(account_id: int, subject: str, page: int, detail: str | None = None) -> None:
    with closing(webapp_conn()) as conn, conn:
        conn.execute(
            "UPDATE source_links SET attempts=attempts+1,detail=COALESCE(?,detail),updated_at=? "
            "WHERE account_id=? AND lower(subject_name)=lower(?) AND page=? AND part_kind IN ('book','unknown')",
            (detail, now_iso(), account_id, subject, page))


def wanted_pages(account_id: int) -> list[dict]:
    """Was noch zu holen ist, je Buch: genannte Seiten vor Kapitelseiten,
    neueste Einträge zuerst."""
    with closing(webapp_conn()) as conn:
        links = [dict(r) for r in conn.execute(
            "SELECT subject_name,page,MIN(entry_date) AS first_date,MAX(entry_date) AS last_date,MAX(attempts) AS attempts,"
            "MIN(entry_kind='chapter') AS only_chapter "
            "FROM source_links WHERE account_id=? AND status='pending' AND part_kind IN ('book','unknown') "
            "GROUP BY lower(subject_name),page ORDER BY only_chapter, last_date DESC, page", (account_id,))]
    groups: dict[str, dict] = {}
    for link in links:
        if link["attempts"] >= MAX_ATTEMPTS:
            continue
        book, _ = book_and_credentials(account_id, subject=link["subject_name"])
        if not book:
            continue
        group = groups.setdefault(book["title"], {"book": book, "subject": link["subject_name"], "pages": {}, "order": []})
        if link["page"] not in group["pages"]:
            group["order"].append(link["page"])
        group["pages"][link["page"]] = link["first_date"]
    return list(groups.values())


async def collect(account_id: int, budget: int = PAGE_BUDGET) -> dict:
    """Ein Sammellauf für ein Kind. Bindet, holt, legt ab, prüft, gleicht ab."""
    started = datetime.now()
    sync = sources.sync_links(account_id)
    sources.refresh_status(account_id)
    summary = {"account_id": account_id, "links": sync["links"], "fetched": 0, "stored": 0, "verified": 0,
               "blank": 0, "mismatch": 0, "failed": 0, "skipped": None}
    _, credentials = book_and_credentials(account_id, subject="")
    if not credentials:
        summary["skipped"] = "kein IServ-Zugang"
        return summary
    remaining = budget
    # Erst die Struktur: Ohne Inhaltsverzeichnis gibt es keine Kapitelregel.
    # Je Lauf höchstens drei Bücher, jedes einmal.
    from .book_structure import read_toc, toc_state
    read = 0
    for book in _books(account_id):
        if read >= 3 or remaining <= 4:
            break
        if toc_state(account_id, book["title"]) in ("ready", "not_found", "failed", "no_ai"):
            continue
        if (access_of(account_id, book["title"]) or {}).get("status") in ("blank", "viewer_error"):
            continue
        outcome = await read_toc(account_id, book, credentials)
        summary.setdefault("toc", {})[short_title(book["title"])] = outcome.get("state")
        remaining -= len(outcome.get("pages") or [])
        read += 1
    if read:
        sources.sync_links(account_id)
        sources.refresh_status(account_id)
    for group in wanted_pages(account_id):
        if remaining <= 0:
            break
        book, subject = group["book"], group["subject"]
        # Das Budget nimmt die wichtigsten Seiten zuerst (genannte vor
        # Kapitelseiten); geblättert wird dann in Buchreihenfolge.
        pages = sorted(group["order"][:remaining])
        remaining -= len(pages)
        delivery = await fetch_pages(account_id, book, credentials, pages, use_cache=False,
                                     budget=90 + 25 * len(pages))
        summary["fetched"] += len(pages)
        if delivery["status"] == "viewer_error":
            record_access(account_id, book["title"], "viewer_error", detail=delivery.get("detail"))
            for page in pages:
                _bump(account_id, subject, page, delivery.get("stage") or "viewer_error")
            summary["failed"] += len(pages)
            continue
        delivered = {p: image for p, image in delivery["shots"] if p is not None}
        for page in pages:
            image = delivered.get(page)
            if image is None:
                _bump(account_id, subject, page, "nicht erreichbar")
                summary["failed"] += 1
                continue
            if looks_blank(image):
                record_access(account_id, book["title"], "blank", page=page)
                _bump(account_id, subject, page, "leere Seite")
                summary["blank"] += 1
                continue
            record_access(account_id, book["title"], "readable", page=page)
            material_id = store_page(account_id, book, page, image, subject, group["pages"][page])
            summary["stored"] += 1
            row = await analyze_page(account_id, material_id)
            if row and row.get("page_check") == "ok":
                record_access(account_id, book["title"], "proven", page=page, printed=page)
                summary["verified"] += 1
            elif row and row.get("page_check") == "mismatch":
                summary["mismatch"] += 1
                printed = json.loads(row.get("printed_pages") or "[]")
                offset = page - min(printed) if printed else 0
                # Bestellung 50 lieferte 48/49: einmal mit dem Versatz nachbestellen.
                if offset and abs(offset) <= 4 and remaining > 0:
                    remaining -= 1
                    again = await fetch_pages(account_id, book, credentials, [page + offset], use_cache=False,
                                              budget=120)
                    shot = next((image for p, image in again["shots"] if p is not None), None)
                    if shot is not None and not looks_blank(shot):
                        material_id = store_page(account_id, book, page, shot, subject, group["pages"][page])
                        row = await analyze_page(account_id, material_id)
                        if row and row.get("page_check") == "ok":
                            record_access(account_id, book["title"], "proven", page=page, printed=page)
                            summary["verified"] += 1
                            continue
                _bump(account_id, subject, page, f"Seite {', '.join(map(str, printed))} geliefert" if printed else "Seite unklar")
            elif row and row.get("page_check") == "blank":
                record_access(account_id, book["title"], "blank", page=page)
                _bump(account_id, subject, page, "leere Seite")
                summary["blank"] += 1
    sources.refresh_status(account_id)
    summary["seconds"] = round((datetime.now() - started).total_seconds())
    log.info("Quellen für Konto %s eingesammelt: %s", account_id, {k: v for k, v in summary.items() if k != "account_id"})
    return summary


def _books(account_id: int) -> list:
    with closing(webapp_conn()) as conn:
        return conn.execute(
            "SELECT * FROM digital_textbook_catalog WHERE account_id=? AND subject_name IS NOT NULL ORDER BY subject_name",
            (account_id,)).fetchall()


def accounts_with_books() -> list[int]:
    with closing(webapp_conn()) as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT c.account_id FROM digital_textbook_credentials c "
            "JOIN digital_textbook_catalog b ON b.account_id=c.account_id")]


def _last_run(key: str) -> str:
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else ""


def _mark_run(day: str, key: str) -> None:
    with closing(webapp_conn()) as conn, conn:
        conn.execute("INSERT INTO schema_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, day))


async def run_due(now: datetime | None = None) -> list[dict]:
    """Die zwei Läufe des Tages, jeder einmal, sobald seine Stunde erreicht ist."""
    now = now or datetime.now()
    day = today_local().isoformat()
    done = []
    for hour, key in ((NIGHT_HOUR, NIGHT_KEY), (AFTERNOON_HOUR, AFTERNOON_KEY)):
        if now.hour < hour or _last_run(key) == day:
            continue
        _mark_run(day, key)
        for account_id in accounts_with_books():
            try:
                done.append(await collect(account_id))
            except Exception:
                log.warning("Sammellauf für Konto %s abgebrochen", account_id, exc_info=True)
    return done


async def background_loop() -> None:
    await asyncio.sleep(120)
    while True:
        try:
            await run_due()
        except Exception:
            log.warning("Sammellauf verschoben; nächster Versuch später", exc_info=True)
        await asyncio.sleep(600)


# Der Lauf von Hand, aus den Eltern-Einstellungen: anstoßen und nachfragen.
def collect_state(account_id: int) -> dict:
    return job_state((account_id, "collect"))


def start_collect(account_id: int) -> dict:
    async def work():
        return await collect(account_id)
    return start_job((account_id, "collect"), work)
