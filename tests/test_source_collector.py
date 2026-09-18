"""Der Sammellauf: holt die genannten Buchseiten, legt sie ab, prüft sie."""
import json
import sqlite3
from contextlib import closing

from test_learning import env  # noqa: F401
from test_sources import history, LA, SN
from backend import book_structure as bs, db, source_collector as collector, sources, textbook_context as ctx
from backend.secret_store import encrypt_secret
from backend.textbook_browser import CaptureResult, PageShot, looks_blank


def png(marker, blank=False):
    from PIL import Image, ImageDraw
    import io
    # Breit genug, um als scharf zu gelten; sonst holt der Lauf sie gleich neu.
    image = Image.new("RGB", (1900, 300), (245, 245, 245))
    if not blank:
        draw = ImageDraw.Draw(image)
        for y in range(20, 280, 12):
            draw.rectangle((30, y, 1870, y + 5), fill=(marker % 200, 30, 30))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def shelf(title="¡Apúntate! 2", subject="spanisch"):
    # Eine Spanischstunde, damit das Hausaufgabenkürzel „SN" sein Fach findet.
    history(lessons=[(99, '2026-09-01', 'SPANISCH', SN, '')])
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO digital_textbook_catalog(account_id,title,provider,launch_url,subject_name,discovered_at)"
                     " VALUES(1,?,NULL,'https://viewer.example/b',?,'2026-09-01T00:00:00+00:00')", (title, subject))
        # Das Verzeichnis gilt als abgesucht, damit ein Lauf im Test nicht erst
        # blättert — mit dem aktuellen Suchstand, sonst bekäme das Buch eine
        # zweite Chance auf den späteren Seiten (D111).
        conn.execute("INSERT OR IGNORE INTO digital_textbook_access(account_id,book_title,status,checked_at,toc_state,toc_version) "
                     "VALUES(1,?,'unknown','2026-09-01T00:00:00+00:00','not_found',?)", (title, bs.TOC_SEARCH_VERSION))
        conn.execute("INSERT INTO digital_textbook_credentials(account_id,portal_url,username,password_ciphertext,"
                     "verification_status,created_at,updated_at) VALUES(1,'https://gaw-iserv.de','kind',?,'catalog_ready','2026-09-01','2026-09-01')",
                     (encrypt_secret("geheim"),))


def fake_capture(pages_delivered, blank_pages=()):
    calls = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        calls.append(list(pages))
        shots = [PageShot(p, png(p, blank=p in blank_pages)) for p in pages if p in pages_delivered or p in blank_pages]
        return CaptureResult(shots=shots, note="" if len(shots) == len(pages) else "Nicht alle Seiten erreichbar")
    return capture, calls


def fake_analysis(monkeypatch, printed_by_material=None, fits="ja"):
    """Statt der KI: schreibt gedruckte Seitenzahlen und Passung in die Zeile."""
    async def analyze(account_id, material_id):
        with closing(db.webapp_conn()) as conn, conn:
            row = conn.execute("SELECT source_page FROM materials WHERE id=?", (material_id,)).fetchone()
            printed = (printed_by_material or {}).get(row["source_page"], [row["source_page"], row["source_page"] + 1])
            check = "ok" if row["source_page"] in printed else "mismatch"
            conn.execute("UPDATE materials SET analysis_state='ready',content_text='Text der Seite',printed_pages=?,"
                         "page_check=?,fits_quote=? WHERE id=?", (json.dumps(printed), check, fits, material_id))
        return True
    monkeypatch.setattr(collector.analysis, "analyze", analyze)
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) VALUES(1,'2026/27',8,1,1,'now')")


async def test_a_run_fetches_named_book_pages_and_files_them_as_materials(env, monkeypatch):
    history(homework=[(1, 'SN', '#libro, p. 50 vocabulario 4 b', '2026-09-10'),
                      (2, 'SN', 'S. 171 Vokabeln lernen', '2026-09-11'),
                      (3, 'SN', '#cda, p. 28', '2026-09-11')])
    shelf()
    capture, calls = fake_capture({50, 171})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    fake_analysis(monkeypatch)
    summary = await collector.collect(1)
    assert calls == [[50, 171]], "beide Buchseiten in einer Browsersitzung, das Arbeitsheft nie"
    assert summary["stored"] == 2 and summary["verified"] == 2
    with closing(db.webapp_conn()) as conn:
        rows = conn.execute("SELECT kind,origin,source_book,source_page,subject_name,title,mime_type,document_date "
                            "FROM materials ORDER BY source_page").fetchall()
        access = conn.execute("SELECT status,page FROM digital_textbook_access WHERE account_id=1").fetchone()
    assert [tuple(r) for r in rows] == [
        ('book_page', 'book_fetch', '¡Apúntate! 2', 50, 'SPANISCH', '¡Apúntate! 2 S. 50', 'image/jpeg', '2026-09-10'),
        ('book_page', 'book_fetch', '¡Apúntate! 2', 171, 'SPANISCH', '¡Apúntate! 2 S. 171', 'image/jpeg', '2026-09-11')]
    assert tuple(access) == ('proven', 171)
    book = sources.ledger(1)
    only = book['subjects'][0]
    assert only['digital'] == 2 and only['pending'] == 0
    assert [(m['label'], m['pages']) for m in only['missing']] == [('Arbeitsheft', [28])]
    assert book['books'][0]['pages_stored'] == 2 and book['books'][0]['access']['status'] == 'proven'
    # Ein zweiter Lauf hat nichts mehr zu holen.
    assert (await collector.collect(1))["fetched"] == 0


async def test_a_blank_page_is_not_kept_and_the_book_is_marked(env, monkeypatch):
    history(homework=[(1, 'SN', 'libro p. 18', '2026-09-10')])
    shelf()
    capture, _ = fake_capture(set(), blank_pages={18})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    fake_analysis(monkeypatch)
    summary = await collector.collect(1)
    assert summary["blank"] == 1 and summary["stored"] == 0
    with closing(db.webapp_conn()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0
        assert conn.execute("SELECT status FROM digital_textbook_access").fetchone()[0] == 'blank'
        assert conn.execute("SELECT attempts,status FROM source_links").fetchone()[:] == (1, 'pending')


async def test_a_wrong_page_is_reordered_with_the_offset_once(env, monkeypatch):
    """Bestellung 50 lieferte 48/49. Die gedruckte Zahl entscheidet, und der
    Versatz wird einmal nachbestellt."""
    history(homework=[(1, 'SN', 'libro p. 50', '2026-09-10')])
    shelf()
    capture, calls = fake_capture({50, 52})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    state = {"first": True}

    async def analyze(account_id, material_id):
        printed = [48, 49] if state["first"] else [50, 51]
        state["first"] = False
        with closing(db.webapp_conn()) as conn, conn:
            conn.execute("UPDATE materials SET analysis_state='ready',printed_pages=?,page_check=?,fits_quote='ja' WHERE id=?",
                         (json.dumps(printed), "ok" if 50 in printed else "mismatch", material_id))
        return True
    monkeypatch.setattr(collector.analysis, "analyze", analyze)
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) VALUES(1,'2026/27',8,1,1,'now')")
    summary = await collector.collect(1)
    assert calls == [[50], [52]], "einmal die Bestellung, einmal mit Versatz +2"
    assert summary["mismatch"] == 1 and summary["verified"] == 1
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT source_page,page_check FROM materials").fetchone()
    assert tuple(row) == (50, 'ok'), "abgelegt unter der gedruckten Seite, nicht unter der Bestellung"


async def test_the_mentor_takes_stored_pages_without_a_browser(env, monkeypatch):
    history(homework=[(1, 'SN', 'libro p. 50', '2026-09-10')])
    shelf()
    capture, calls = fake_capture({50})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    fake_analysis(monkeypatch)
    await collector.collect(1)
    calls.clear()
    parts, context = await ctx.homework_page_images(1, "Spanisch", "libro p. 50")
    assert calls == [] and context["status"] == "loaded" and len(parts) == 1
    # Eine noch nicht abgelegte Seite wird geholt und landet danach im Bestand.
    capture2, calls2 = fake_capture({51})
    monkeypatch.setattr(ctx, "capture_pages", capture2)
    parts, context = await ctx.homework_page_images(1, "Spanisch", "S. 50-51")
    assert calls2 == [[51]] and context["status"] == "loaded"
    with closing(db.webapp_conn()) as conn:
        assert [r[0] for r in conn.execute("SELECT source_page FROM materials ORDER BY source_page")] == [50, 51]


async def test_the_two_daily_runs_fire_once_each(env, monkeypatch):
    from datetime import datetime
    shelf()
    runs = []

    async def collect(account_id, budget=40):
        runs.append(account_id)
        return {"account_id": account_id}
    monkeypatch.setattr(collector, "collect", collect)
    await collector.run_due(datetime(2026, 9, 15, 8, 0))
    assert runs == [1], "nach zwei Uhr: der Nachtlauf, sonst nichts"
    await collector.run_due(datetime(2026, 9, 15, 9, 0))
    assert runs == [1], "derselbe Lauf nicht zweimal am Tag"
    await collector.run_due(datetime(2026, 9, 15, 14, 5))
    assert runs == [1, 1], "um vierzehn Uhr der zweite"
    await collector.run_due(datetime(2026, 9, 15, 23, 0))
    assert runs == [1, 1]


def test_short_titles_are_readable():
    assert collector.short_title("BiBox Mathematik Neue Wege 8 Gymnasium G9 Niedersachsen") == "Mathematik Neue Wege 8"
    assert collector.short_title("Deutschbuch Gymnasium - Niedersachsen - Ausgabe 2019 · 8. Schuljahr - E-Book") == "Deutschbuch"
    assert collector.short_title("¡Apúntate! - Spanisch als 2. Fremdsprache - Ausgabe 2016 · Band 2 - E-Book") == "¡Apúntate!"


async def test_book_pages_stop_before_the_storage_of_the_child_is_full(env, monkeypatch):
    history(homework=[(1, 'SN', 'libro p. 50-52', '2026-09-10')])
    shelf()
    capture, calls = fake_capture({50, 51, 52})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    fake_analysis(monkeypatch)
    monkeypatch.setattr(collector, "to_jpeg", lambda blob, max_side=1600: b"x" * 60_000)
    from backend import materials
    monkeypatch.setattr(materials, "MAX_ACCOUNT_FILES", 150_000)
    summary = await collector.collect(1)
    assert summary["stored"] == 2 and summary["skipped"] == "Materialspeicher voll", "90 Prozent von 150 KB: zwei Seiten passen, die dritte nicht"
    with closing(db.webapp_conn()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 2


async def test_pages_left_unread_are_read_before_new_fetches(env, monkeypatch):
    """Der KI-Rahmen war erschöpft: die Seiten liegen da, ungelesen. Der
    nächste Lauf liest sie zuerst und weist damit das Buch nach."""
    history(homework=[(1, 'SN', 'libro p. 50', '2026-09-10')])
    shelf()
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,analysis_state,"
                     "analysis_error,created_at,updated_at) VALUES(1,'book_page','SPANISCH','S. 50','book_fetch','¡Apúntate! 2',50,"
                     "'failed','429','now','now')")
    capture, calls = fake_capture({50})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    fake_analysis(monkeypatch)
    summary = await collector.collect(1)
    assert calls == [], "die Seite liegt da, nichts wird geholt"
    assert summary["reread"] == 1 and summary["verified"] == 1
    with closing(db.webapp_conn()) as conn:
        assert conn.execute("SELECT status FROM digital_textbook_access").fetchone()[0] == 'proven'
        assert conn.execute("SELECT status,detail FROM source_links").fetchone()[:] == ('digital', 'belegt')


async def test_two_runs_for_the_same_child_do_not_overlap(env, monkeypatch):
    import asyncio
    shelf()
    gate = asyncio.Event()

    async def slow(account_id, budget):
        await gate.wait()
        return {"account_id": account_id, "fetched": 0, "stored": 0, "verified": 0, "skipped": None}
    monkeypatch.setattr(collector, "_collect", slow)
    first = asyncio.create_task(collector.collect(1))
    await asyncio.sleep(0.01)
    second = await collector.collect(1)
    assert second["skipped"] == "läuft bereits"
    gate.set()
    assert (await first)["skipped"] is None
    assert (await collector.collect(1))["skipped"] is None, "nach dem Ende ist der Weg wieder frei"


async def test_blurry_pages_from_earlier_runs_get_a_sharper_image_without_a_new_analysis(env, monkeypatch):
    shelf()
    from PIL import Image
    import io
    small = io.BytesIO(); Image.new("RGB", (640, 900), (250, 250, 250)).save(small, "JPEG")
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,page_check,analysis_state,"
                     "content_text,file_bytes,mime_type,created_at,updated_at) VALUES(1,'book_page','SPANISCH','S. 50','book_fetch','¡Apúntate! 2',50,"
                     "'ok','ready','Text bleibt',?, 'image/jpeg','now','now')", (small.getvalue(),))

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        big = io.BytesIO(); img = Image.new("RGB", (2600, 1800), (250, 250, 250))
        from PIL import ImageDraw
        ImageDraw.Draw(img).rectangle((100, 100, 2400, 1600), fill=(40, 40, 40)); img.save(big, "PNG")
        return CaptureResult(shots=[PageShot(p, big.getvalue()) for p in pages])
    monkeypatch.setattr(ctx, "capture_pages", capture)
    _, credentials = ctx.book_and_credentials(1, subject="")
    assert await collector.resharpen(1, credentials, 20) == 1
    with closing(db.webapp_conn()) as conn:
        row = conn.execute("SELECT file_bytes,analysis_state,content_text FROM materials").fetchone()
    assert Image.open(io.BytesIO(row["file_bytes"])).width == 2400 and row["analysis_state"] == "ready" and row["content_text"] == "Text bleibt"
    assert await collector.resharpen(1, credentials, 20) == 0, "einmal scharf bleibt scharf"


def test_pages_of_open_homework_and_exam_subjects_come_first(env):
    history(lessons=[(1, '2026-09-01', 'LATEIN', LA, ''), (2, '2026-09-14', 'SPANISCH', SN, 'libro p. 70')],
            homework=[(7, 'LA', 'TB S. 13', '2026-09-10'), (8, 'SN', 'libro p. 50', '2026-09-08')])
    shelf()
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'latein','Prima','now')")
        c.execute("INSERT INTO tasks(account_id,title,task_type,status,source,notes,subject_name,created_at,updated_at) "
                  "VALUES(1,'Latein','homework','open','ha_todo','TB S. 13\n[LA7]','LATEIN','now','now')")
    sources.ledger(1)
    plain = collector.wanted_pages(1)
    assert [g["subject"] for g in plain] == ["SPANISCH", "LATEIN"], "ohne Vorrang zählt das Datum: die Spanischstunde ist neuer"
    priority = {"homework_pages": {("latein", 13)}, "exam_subjects": set()}
    assert [g["subject"] for g in collector.wanted_pages(1, priority)] == ["LATEIN", "SPANISCH"], "die offene Hausaufgabe zuerst"
    priority = {"homework_pages": set(), "exam_subjects": {"spanisch"}}
    groups = collector.wanted_pages(1, priority)
    assert groups[0]["subject"] == "SPANISCH" and groups[0]["order"][0] in (50, 70)


async def test_pages_the_session_never_reached_keep_their_attempts(env, monkeypatch):
    """Eine Browsersitzung hat ein Zeitbudget. Was sie nicht mehr geschafft hat,
    darf nicht als Fehlversuch der Seite zählen: Sonst verbraucht eine große
    Bestellung die drei Versuche der hinteren Seiten, ohne dass sie je geöffnet
    wurden, und sie werden nie wieder geholt. Genau daran stand der Abruf der
    englischen Vokabelseiten still, während die Bilanz sie als offen führte (D112)."""
    history(homework=[(1, 'SN', 'libro p. 50, 51, 52', '2026-09-10')])
    shelf()
    calls = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        calls.append(list(pages))
        # Nur die erste Seite schafft die Sitzung, dann ist die Zeit um.
        return CaptureResult(shots=[PageShot(pages[0], png(pages[0]))], note="Zeitbudget erreicht")
    monkeypatch.setattr(ctx, "capture_pages", capture)
    fake_analysis(monkeypatch)
    summary = await collector.collect(1)
    assert summary["deferred"] == 2 and summary["failed"] == 0
    with closing(db.webapp_conn()) as conn:
        attempts = {r["page"]: r["attempts"] for r in conn.execute(
            "SELECT page,attempts FROM source_links WHERE account_id=1 AND page IN (50,51,52)")}
    assert attempts == {50: 0, 51: 0, 52: 0}, attempts
    # Eine Sitzung bestellt nicht mehr, als sie schafft.
    assert all(len(c) <= collector.PAGES_PER_SESSION for c in calls), calls
    # Eine Seite, die der Viewer wirklich nicht liefert, zählt weiterhin.
    async def empty(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        return CaptureResult(shots=[], note="")
    monkeypatch.setattr(ctx, "capture_pages", empty)
    await collector.collect(1)
    with closing(db.webapp_conn()) as conn:
        assert conn.execute("SELECT MAX(attempts) FROM source_links WHERE account_id=1").fetchone()[0] >= 1
