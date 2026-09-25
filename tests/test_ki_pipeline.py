"""KI- und Materialpipeline: bezahlte Wiederholungen begrenzt, eine Lesung
zugleich, Kalender nicht durch einen gestörten Abruf geleert, Kostenrahmen
meldet statt sperrt."""
import asyncio
import io
import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, ai_env  # noqa: F401
from backend import db, ai_gateway as ai, material_analysis as analysis, materials as store
from backend import page_figures, school_calendars, iserv_portal, source_collector as collector, triggers
from backend.auth import get_current_user
from backend.routers import materials as materials_router


def utc(**delta) -> str:
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


def jpeg(size=(400, 600)) -> bytes:
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, format="JPEG")
    return out.getvalue()


def material(kind="book_page", state="pending", **extra) -> int:
    fields = {"account_id": 1, "kind": kind, "subject_name": "PHYSIK", "title": "Seite", "content_text": "",
              "mime_type": "image/jpeg", "file_bytes": jpeg(), "analysis_state": state,
              "created_at": utc(hours=-2), "updated_at": utc(hours=-2), **extra}
    with closing(db.webapp_conn()) as c:
        return c.execute(f"INSERT INTO materials({','.join(fields)}) VALUES({','.join('?' * len(fields))})",
                         tuple(fields.values())).lastrowid


def column(material_id, name):
    with closing(db.webapp_conn()) as c:
        return c.execute(f"SELECT {name} FROM materials WHERE id=?", (material_id,)).fetchone()[0]


def profile():
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at)"
                  " VALUES(1,'2026/2027',8,1,1,'2026-09-01')")


# --------------------------------------------------------------- Abbildungen

def scans(material_id):
    with closing(db.webapp_conn()) as c:
        row = c.execute("SELECT * FROM material_figure_scans WHERE material_id=?", (material_id,)).fetchone()
    return dict(row) if row else None


def test_an_incomplete_figure_answer_is_not_bought_again_every_ten_minutes(env, monkeypatch):
    """Bis 1.31.2 warf ai.complete bei unvollständiger Antwort 502, der Lauf
    brach ab, ohne die Seite zu vermerken, und nahm sie zehn Minuten später
    wieder: dieselbe Seite, jedes Mal bezahlt."""
    first, second = material(), material()
    calls = []

    async def complete(account, purpose, instruction, context, images=None, **kw):
        calls.append(context["seite"])
        raise HTTPException(502, "unvollständig")
    monkeypatch.setattr(ai, "complete", complete)
    monkeypatch.setattr(page_figures, "STOP_AFTER_FAILURES", 5)
    assert asyncio.run(page_figures.cycle()) == 0
    assert len(calls) == 2, "nach einem Fehlversuch geht es mit der nächsten Seite weiter"
    assert scans(first)["attempts"] == 1 and scans(second)["attempts"] == 1
    assert "502" in scans(first)["error"]
    assert page_figures.pending() == [], "erst nach der Pause wieder"
    # Nach der Pause (6 h je Versuch) kommt die Seite wieder dran, nach drei Versuchen nie mehr.
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE material_figure_scans SET scanned_at=?", ((datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),))
    assert set(page_figures.pending()) == {(1, first), (1, second)}
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE material_figure_scans SET attempts=3")
    assert page_figures.pending() == []


def test_other_errors_count_too_and_a_budget_stop_ends_the_run(env, monkeypatch):
    first, second = material(), material()

    async def broken(*a, **kw):
        raise AttributeError("'NoneType' object has no attribute 'strip'")
    monkeypatch.setattr(ai, "complete", broken)
    monkeypatch.setattr(page_figures, "STOP_AFTER_FAILURES", 5)
    asyncio.run(page_figures.cycle())
    assert scans(second)["attempts"] == 1 and "AttributeError" in scans(second)["error"]
    third = material()
    calls = []

    async def budget(*a, **kw):
        calls.append(1)
        raise HTTPException(409, "Bitte bestätigen")
    monkeypatch.setattr(ai, "complete", budget)
    asyncio.run(page_figures.cycle())
    assert calls == [1], "ein Rahmen- oder Einrichtungsfehler beendet den Lauf"
    assert scans(third) is None, "und zählt nicht als Versuch"


def test_two_failures_in_a_row_end_the_run(env, monkeypatch):
    for _ in range(4):
        material()
    calls = []

    async def down(*a, **kw):
        calls.append(1)
        raise HTTPException(502, "Anbieter gestört")
    monkeypatch.setattr(ai, "complete", down)
    asyncio.run(page_figures.cycle())
    assert len(calls) == page_figures.STOP_AFTER_FAILURES


def test_old_error_marks_stay_done(env):
    """Einträge mit Fehler von früher (ohne Versuchszähler) gelten weiter als erledigt."""
    mid = material()
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO material_figure_scans(material_id,account_id,scanned_at,count,error) "
                  "VALUES(?,1,'2026-01-01T00:00:00+01:00',0,'unlesbar: alt')", (mid,))
    assert page_figures.pending() == []


# --------------------------------------------------------------- Kalender

def _calendar_env(monkeypatch, answers):
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_credentials(account_id,portal_url,username,password_ciphertext,created_at,updated_at) "
                  "VALUES(1,'https://beispiel-iserv.de','kind','x','2026-09-01','2026-09-01')")
    plugin = "https://beispiel-iserv.de/iserv/calendar4/plugin?plugin=exam-plan"
    monkeypatch.setattr(school_calendars, "decrypt_secret", lambda value: "geheim")

    async def discover(*a):
        return []

    async def sources(*a):
        return [{"url": plugin, "name": "Klausurplan"}]

    async def portal_json(portal, user, password, paths):
        return {p: answers["v"] for p in paths if answers["v"] is not None}
    monkeypatch.setattr(school_calendars.iserv_calendar, "discover", discover)
    monkeypatch.setattr(iserv_portal, "sources", sources)
    monkeypatch.setattr(iserv_portal, "portal_json", portal_json)


EXAM = {"id": "exam-1", "title": "Physikarbeit", "start": f"{date.today().isoformat()}T08:00:00+02:00",
        "end": f"{date.today().isoformat()}T09:30:00+02:00", "allDay": False}


def stored_events():
    with closing(db.webapp_conn()) as c:
        return [r[0] for r in c.execute("SELECT uid FROM iserv_calendar_events")]


def test_a_missing_plugin_answer_keeps_the_exam_plan(env, monkeypatch):
    """Bis 1.31.2 löschte ein Fehlerstatus oder eine leere Antwort den ganzen
    Klausurplan im Fenster, weil parse_plugin(None) eine leere Liste lieferte."""
    answers = {"v": [EXAM]}
    _calendar_env(monkeypatch, answers)
    asyncio.run(school_calendars.sync(1))
    assert stored_events() == ["exam-1"]
    for broken in (None, {"error": "kaputt"}, "text"):
        answers["v"] = broken
        state = asyncio.run(school_calendars.sync(1))
        assert stored_events() == ["exam-1"], broken
        assert state["status"] == "ready" and "bisherige Termine bleiben" in state["error"]
    # Eine echte Liste ersetzt, auch eine leere: ein abgesagter Termin verschwindet.
    answers["v"] = []
    state = asyncio.run(school_calendars.sync(1))
    assert stored_events() == [] and state["status"] == "ready" and not state["error"]


def test_a_broken_plugin_entry_is_skipped_not_fatal():
    start, end = date(2026, 9, 1), date(2026, 10, 31)
    good = {"id": "ok", "title": "Arbeit", "start": "2026-09-24T07:50:00+02:00", "end": "2026-09-24T09:25:00+02:00"}
    data = ["kein Eintrag", {"id": "x", "start": "kein Datum"}, {"id": "y", "start": 17}, good,
            {"id": "z", "start": "2026-09-25T08:00:00+02:00", "displayFields": "komisch"}]
    events = iserv_portal.parse_plugin(data, start, end)
    assert [e["uid"] for e in events] == ["ok", "z"]


# --------------------------------------------------------------- Materialauswertung

def _reader(monkeypatch, calls, gate=None, fail=None):
    async def read_material(account_id, row):
        calls.append(row["id"])
        if gate is not None:
            await gate.wait()
        if fail is not None:
            raise fail
        return analysis.Insight(kind="book_page", content_text="Text", confidence=0.9), "hoch"
    monkeypatch.setattr(analysis, "read_material", read_material)

    async def after(*a):
        return None
    monkeypatch.setattr(analysis, "after_analysis", after)


def test_one_reading_at_a_time_per_material(env, monkeypatch):
    """Nachtlauf, Sammellauf, Wiederholung, Upload und „Neu auswerten“ lasen
    bis 1.31.2 dieselbe Seite parallel und bezahlten sie doppelt."""
    mid = material()
    calls = []

    async def run():
        gate = asyncio.Event()
        _reader(monkeypatch, calls, gate)
        first = asyncio.create_task(analysis.analyze(1, mid))
        await asyncio.sleep(0.05)
        assert analysis.is_reading(mid)
        second = await analysis.analyze(1, mid)
        gate.set()
        return await first, second
    first, second = asyncio.run(run())
    assert calls == [mid] and first is True and second is False
    assert column(mid, "analysis_state") == "ready" and column(mid, "analysis_claimed_at") is None
    assert not analysis.is_reading(mid)


def test_a_stale_claim_expires_after_a_crash(env, monkeypatch):
    mid = material()
    calls = []
    _reader(monkeypatch, calls)
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_claimed_at=? WHERE id=?", (utc(minutes=-5), mid))
    assert asyncio.run(analysis.analyze(1, mid)) is False and calls == []
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_claimed_at=? WHERE id=?", (utc(minutes=-analysis.CLAIM_MINUTES - 1), mid))
    assert asyncio.run(analysis.analyze(1, mid)) is True and calls == [mid]


def test_a_failure_releases_the_claim_and_counts(env, monkeypatch):
    mid = material()
    _reader(monkeypatch, [], fail=HTTPException(502, "x"))
    assert asyncio.run(analysis.analyze(1, mid)) is False
    assert column(mid, "analysis_claimed_at") is None
    assert column(mid, "analysis_attempts") == 1 and column(mid, "analysis_error") == "502"
    # Ein Rahmen- oder Einrichtungsfehler hat nichts gekostet und zählt nicht.
    _reader(monkeypatch, [], fail=HTTPException(503, "x"))
    asyncio.run(analysis.analyze(1, mid))
    assert column(mid, "analysis_attempts") == 1
    # Eine gelungene Lesung setzt zurück.
    _reader(monkeypatch, [])
    assert asyncio.run(analysis.analyze(1, mid)) is True
    assert column(mid, "analysis_attempts") == 0 and column(mid, "analysis_failed_at") is None


def test_an_unreadable_material_is_not_paid_for_every_night(env, monkeypatch):
    """due() nahm jedes gescheiterte Material jede Nacht, die Wiederholungen
    zählten nur im Speicher. Jetzt zählt das Material selbst, mit wachsender
    Pause und nach fünf Fehlversuchen gar nicht mehr von selbst."""
    profile()
    mid = material(state="failed", analysis_error="502")
    assert (1, mid) in analysis.due()
    now = datetime.now(timezone.utc)
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_attempts=2,analysis_failed_at=? WHERE id=?",
                  ((now - timedelta(hours=1)).isoformat(), mid))
    assert (1, mid) not in analysis.due(), "Pause nach dem zweiten Versuch"
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_failed_at=? WHERE id=?", ((now - timedelta(hours=7)).isoformat(), mid))
    assert (1, mid) in analysis.due()
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_attempts=5,analysis_failed_at=? WHERE id=?",
                  ((now - timedelta(days=30)).isoformat(), mid))
    assert (1, mid) not in analysis.due()
    triggers._RETRIES.clear()
    monkeypatch.setattr(triggers, "now_iso", lambda: utc())
    assert (1, mid) not in triggers.failed_materials()
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET origin='book_fetch' WHERE id=?", (mid,))
    assert mid not in collector._unread_pages(1, 40)


def test_the_manual_button_starts_over_and_says_when_a_reading_runs(env, monkeypatch):
    _, state, _ = env
    app = FastAPI()
    app.include_router(materials_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    client = TestClient(app)
    mid = material(state="failed")
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_attempts=5,analysis_failed_at=?,analysis_claimed_at=? WHERE id=?",
                  (utc(), utc(), mid))
    started = []

    async def analyze(account_id, material_id):
        started.append(material_id)
        return True
    monkeypatch.setattr(analysis, "analyze", analyze)
    r = client.post(f"/api/accounts/1/materials/{mid}/analysis")
    assert r.status_code == 200 and r.json()["running"] is True and started == []
    assert column(mid, "analysis_attempts") == 0
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_claimed_at=NULL WHERE id=?", (mid,))
    r = client.post(f"/api/accounts/1/materials/{mid}/analysis")
    assert r.status_code == 200 and r.json()["queued"] is True and started == [mid]


# --------------------------------------------------------------- Doppelseiten

def test_printed_pages_are_read_as_json_and_the_old_comma_form():
    assert store.printed_list("[160, 161]") == [160, 161]
    assert store.printed_list("160,161") == [160, 161]
    assert store.printed_list(None) == [] and store.printed_list("") == [] and store.printed_list("kaputt") == []
    assert store.printed_list("12") == [12] and store.printed_list([3, "4"]) == [3, 4]


def test_the_second_page_of_a_spread_matches_the_task(env):
    """printed_pages ist JSON; bis 1.31.2 zerlegten zwei Stellen es am Komma,
    und „161]“ passte nie auf S. 161."""
    from backend import sources
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO tasks(id,account_id,title,notes,subject_name,status,source,created_at,updated_at) "
                  "VALUES(930,1,'Ah S. 161, Aufg. 2','','DEUTSCH','open','untis','2026-09-17','2026-09-17')")
    mid = material(kind="workbook", state="ready", subject_name="DEUTSCH", source_label="Arbeitsheft",
                   source_page=160, printed_pages="[160, 161]", pupil_entries=1, handwritten=1, origin="")
    hits = sources.task_candidates(1, 930)
    assert hits and hits[0]["material_id"] == mid and "161" in hits[0]["reason"]
    found = sources.solution_for_task(1, 930)
    assert found and found["material_id"] == mid


# --------------------------------------------------------------- Buchseitenabruf

def test_old_fetch_attempts_expire(env, monkeypatch):
    """Nach drei Fehlversuchen blieb eine Seite bis 1.31.2 für immer liegen."""
    old = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    with closing(db.webapp_conn()) as c:
        for page, stamp in ((50, old), (51, fresh)):
            c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,"
                      "page,attempts,synced_at,updated_at) VALUES(1,'homework',1,'2026-09-10','SPANISCH','Buch','book',?,3,?,?)",
                      (page, stamp, stamp))
    assert collector.expire_attempts(1) == 1
    with closing(db.webapp_conn()) as c:
        attempts = dict(c.execute("SELECT page,attempts FROM source_links").fetchall())
    assert attempts == {50: 0, 51: 3}


def test_software_webgl_is_tried_again_after_an_hour(monkeypatch):
    from backend import textbook_browser as tb
    started = []

    def start(arguments):
        started.append("--use-angle=vulkan" in arguments)
        if started[-1]:
            raise RuntimeError("kein GPU-Prozess")
        return object()
    monkeypatch.setattr(tb, "_start", start)
    monkeypatch.setattr(tb, "_SOFTWARE_WEBGL_WORKS", None)
    monkeypatch.setattr(tb, "_SOFTWARE_WEBGL_FAILED_AT", None)
    clock = {"t": 1000.0}
    monkeypatch.setattr(tb.time, "monotonic", lambda: clock["t"])
    tb._driver()
    tb._driver()
    assert started == [True, False, False], "nach dem Fehlschlag erst einmal ohne GPU"
    clock["t"] += tb.SOFTWARE_WEBGL_RETRY + 1
    tb._driver()
    assert started[-2:] == [True, False], "nach einer Stunde wieder mit Software-WebGL versucht"


# --------------------------------------------------------------- Gateway

class _Client:
    """Ein AsyncClient-Ersatz mit fester Antwort oder festem Fehler."""
    seen: list = []

    def __init__(self, answer):
        self.answer = answer

    def __call__(self, **kw):
        _Client.seen.append(kw)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def post(self, url, **kw):
        if isinstance(self.answer, Exception):
            raise self.answer
        return httpx.Response(200, json=self.answer, request=httpx.Request("POST", url))


def _calls():
    with closing(db.webapp_conn()) as c:
        return [dict(r) for r in c.execute("SELECT status,error FROM mentor_ai_calls")]


def test_a_connect_timeout_releases_the_reservation(env):
    """Eine Zeitüberschreitung beim Verbindungsaufbau hat nichts gekostet; bis
    1.31.2 blieb ihre Reservierung als „provider_error“ stehen."""
    _, _, patch = env
    ai_env(patch)
    patch.setattr(ai.httpx, "AsyncClient", _Client(httpx.ConnectTimeout("keine Verbindung")))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ai.complete(1, "mentor", "x", {}))
    assert exc.value.status_code == 502
    assert _calls()[0]["status"] == "released"
    timeout = _Client.seen[-1]["timeout"]
    assert isinstance(timeout, httpx.Timeout) and timeout.connect == 15 and timeout.read >= 90


def test_chat_completions_without_content_is_a_502_not_a_crash(env):
    _, _, patch = env
    ai_env(patch, url="https://example.com/openai/deployments/x/chat/completions")
    answer = {"choices": [{"message": {"content": None}, "finish_reason": "length"}],
              "usage": {"prompt_tokens": 10, "completion_tokens": 256}}
    patch.setattr(ai.httpx, "AsyncClient", _Client(answer))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ai.complete(1, "mentor", "x", {}))
    assert exc.value.status_code == 502
    assert _calls()[0]["status"] == "settled", "bezahlt ist bezahlt: gebucht wird trotzdem"


def test_images_are_prepared_off_the_event_loop(env):
    """Die Bildaufbereitung läuft in einem Thread; das Ergebnis bleibt gleich."""
    import base64
    import threading
    _, _, patch = env
    ai_env(patch)
    threads = []
    real = ai.page_images

    def page_images(pages, model):
        threads.append(threading.current_thread() is threading.main_thread())
        return real(pages, model)
    patch.setattr(ai, "page_images", page_images)
    answer = {"status": "completed", "usage": {"input_tokens": 100, "output_tokens": 10},
              "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "{}"}]}]}
    patch.setattr(ai.httpx, "AsyncClient", _Client(answer))
    image = {"type": "image_url", "page": True,
             "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg()).decode()}}
    raw, _, _ = asyncio.run(ai.complete(1, "mentor", "x", {}, [image]))
    assert raw == "{}" and threads == [False]


def test_the_projection_does_not_count_last_month_at_the_start_of_a_month(env):
    """Am 2. eines Monats standen bis 1.31.2 fünf Vormonatstage im Fenster,
    geteilt durch zwei Tage: die Hochrechnung lag weit zu hoch."""
    with closing(db.webapp_conn()) as c:
        for day, micro in (("2026-09-28", 5_000_000), ("2026-09-30", 5_000_000), ("2026-10-01", 1_000_000),
                           ("2026-10-02", 1_000_000)):
            c.execute("INSERT INTO mentor_ai_calls(id,account_id,purpose,month,day,model,status,reserved_micro,charged_micro,"
                      "input_rate,output_rate,created_at) VALUES(?,1,'mentor',?,?,'test','settled',?,?,1,1,?)",
                      (day, day[:7], day, micro, micro, day))
        projected, per_day = ai.projection(c, "2026-10", 2_000_000, date(2026, 10, 2))
    assert per_day == 1.0
    assert projected == 2.0 + 29 * 1.0
    with closing(db.webapp_conn()) as c:
        # Ab dem siebten Tag unverändert: sieben Tage, geteilt durch sieben.
        _, per_day = ai.projection(c, "2026-10", 2_000_000, date(2026, 10, 8))
    assert per_day == round(1_000_000 / 7 / 1e6, 3)


def test_an_overrun_lock_from_before_is_lifted_on_update(env):
    """Die Migration löst eine Sperre, die nur eine Überschreitung gesetzt hat."""
    with closing(db.webapp_conn()) as c:
        ai.init_config(c)
        c.execute("UPDATE mentor_ai_config SET opening_month='2026-09',opening_confirmed=0 WHERE id=1")
        c.execute("INSERT INTO mentor_ai_calls(id,account_id,purpose,month,day,model,status,reserved_micro,charged_micro,"
                  "input_rate,output_rate,created_at) VALUES('o',1,'mentor','2026-09','2026-09-11','test','settled',10,99,1,1,'x')")
        c.execute("DELETE FROM schema_meta WHERE key='migration:opt_ki_005_overrun_unlock'")
    db.init_webapp_db()
    assert ai.status()["opening_confirmed"]


def test_a_real_opening_is_not_lifted(env):
    with closing(db.webapp_conn()) as c:
        ai.init_config(c)
        c.execute("UPDATE mentor_ai_config SET opening_month='2026-09',opening_confirmed=0 WHERE id=1")
        c.execute("DELETE FROM schema_meta WHERE key='migration:opt_ki_005_overrun_unlock'")
    db.init_webapp_db()
    assert not ai.status()["opening_confirmed"]


# --------------------------------------------------------------- Auslieferung, Löschen

def test_a_filename_outside_latin1_is_delivered(env):
    """Header sind Latin-1: „Übung ✓.jpg“ ließ die Auslieferung bis 1.31.2 mit 500 scheitern."""
    _, state, _ = env
    app = FastAPI()
    app.include_router(materials_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    client = TestClient(app)
    mid = material(filename='Übung "1" ✓.jpg')
    r = client.get(f"/api/accounts/1/materials/{mid}/file")
    assert r.status_code == 200
    header = r.headers["content-disposition"]
    assert header.startswith('inline; filename="Ubung _1_ .jpg"')
    assert "filename*=UTF-8''%C3%9Cbung%20%221%22%20%E2%9C%93.jpg" in header


def test_removing_with_a_foreign_account_keeps_the_links(env):
    mid = material()
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO material_links(material_id,kind,target_id,origin,created_at) VALUES(?,'task',7,'mensch','x')", (mid,))
    assert store.remove(2, mid) is False
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM material_links WHERE material_id=?", (mid,)).fetchone()[0] == 1
    assert store.remove(1, mid) is True
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM material_links WHERE material_id=?", (mid,)).fetchone()[0] == 0


# --------------------------------------------------------------- Kapitel

def test_a_reread_table_of_contents_keeps_the_entry_chapters(env):
    """Neu gelesene Kapitel bekamen neue Nummern; die Zuordnungen der
    Stundeneinträge zeigten danach ins Leere und wurden nie neu gesetzt."""
    from backend import book_structure as bs
    from backend.book_structure import Chapter
    title = "Physikbuch"
    toc = [Chapter(number="1", title="Stromkreise", start_page=10, level=1),
           Chapter(number="2", title="Magnetismus", start_page=30, level=1)]
    bs.store_chapters(1, title, toc)
    ids = {c["number"]: c["id"] for c in bs.chapters_of(1, title)}
    with closing(db.webapp_conn()) as c:
        for entry_id, number in ((1, "1"), (2, "2")):
            c.execute("INSERT INTO entry_chapters(account_id,entry_kind,entry_id,entry_date,subject_name,book_title,chapter_id,"
                      "confidence,origin,text_hash,created_at) VALUES(1,'lesson',?,'2026-09-10','PHYSIK',?,?,0.9,'ai','h','x')",
                      (entry_id, title, ids[number]))
    bs.store_chapters(1, title, [toc[0], Chapter(number="2", title="Wärme", start_page=30, level=1)])
    now = {c["number"]: c["id"] for c in bs.chapters_of(1, title)}
    with closing(db.webapp_conn()) as c:
        rows = dict(c.execute("SELECT entry_id,chapter_id FROM entry_chapters").fetchall())
    assert rows == {1: now["1"]}, "gleiches Kapitel folgt, ein verschwundenes wird neu zugeordnet"
    assert now["1"] != ids["1"]
