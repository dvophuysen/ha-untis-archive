"""Korrekturen im Lernbereich: Test-Rückbau, Kontext-Stand, Budget, Sperren,
Buchseiten, Verfassung, Chips, Schultage, Geräterolle, Schreibrechte, Zeitzone."""
import asyncio
import json
import random
import sqlite3
import time
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

import pytest

from test_learning import env, seed, child, P, path, ai_env  # noqa: F401
from test_mentor import setup, mock, send, start, reply, B, TASK  # noqa: F401
from test_lernstand import exam_env, topic_reply  # noqa: F401
from backend import db, lernstand, mentor_context as mc, practice, learning_compass as lc, learning_plan as lp
from backend import ai_gateway as ai, view_mode
from backend.routers import mentor as m


# ------------------------------------------------------------ K11 Test-Rückbau

def topic_session(client, patch, tid, answers=3):
    mock(patch, [topic_reply("Bilde", None)])
    s = client.post(B + "/sessions", json={"subject": "Latein", "topic_id": tid}).json()
    s = send(client, s, text="Gleich eine Aufgabe").json()
    for op in ("Erkenne", "Übersetze", "Wende an")[:answers]:
        mock(patch, [topic_reply(op, "correct")])
        s = send(client, s, kind="answer", text="servi", seconds=6, edits=0).json()
    return s


def counted(tid):
    with closing(db.webapp_conn()) as c:
        return (c.execute("SELECT COUNT(*) FROM topic_answers WHERE topic_id=?", (tid,)).fetchone()[0],
                c.execute("SELECT stage FROM exam_topics WHERE id=?", (tid,)).fetchone()[0])


def test_only_a_test_takes_the_topic_answers_out_and_back_in(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "a-/o-Deklination")["id"]
    # Eine Übungsarbeit auf Papier (negative session_id) bleibt unberührt.
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO topic_answers(account_id,topic_id,session_id,result,afb,created_at,source) "
                  "VALUES(1,?,-7,'incorrect',1,'2026-09-10T10:00:00+02:00','paper')", (tid,))
    s = topic_session(client, patch, tid)
    n, stage_before = counted(tid)
    assert n == 4 and stage_before in ("wackelt", "sitzt")
    r = client.put(B + f"/sessions/{s['id']}/counts", json={"counts": False})
    assert r.status_code == 200 and r.json()["is_test"] == 1
    n, stage = counted(tid)
    assert n == 1 and stage == "angefangen", "nur die Papierantwort zählt noch"
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers_void WHERE session_id=?", (s["id"],)).fetchone()[0] == 3
        raster = practice.raster(1, "cal:latein-2026-09-21")
    assert sum(cell["tasks"] for row in raster["topics"] for cell in row["cells"].values()) == 1, "nur die Papierantwort"
    # „Zählt doch“: die Antworten kommen mit ihrer ID zurück, die Stufe auch.
    before = [r[0] for r in db.webapp_conn().execute("SELECT id FROM topic_answers_void ORDER BY id")]
    assert client.put(B + f"/sessions/{s['id']}/counts", json={"counts": True}).json()["is_test"] == 0
    n, restored = counted(tid)
    assert n == 4 and restored == stage_before
    with closing(db.webapp_conn()) as c:
        ids = [r[0] for r in c.execute("SELECT id FROM topic_answers WHERE session_id=? ORDER BY id", (s["id"],))]
        assert ids == before and c.execute("SELECT COUNT(*) FROM topic_answers_void").fetchone()[0] == 0


def test_a_taken_id_gets_a_new_one_on_restore(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Zahlwörter")["id"]
    s = topic_session(client, patch, tid, answers=2)
    client.put(B + f"/sessions/{s['id']}/counts", json={"counts": False})
    # Inzwischen vergibt die Datenbank die frei gewordenen IDs neu.
    with closing(db.webapp_conn()) as c, c:
        for _ in range(3):
            c.execute("INSERT INTO topic_answers(account_id,topic_id,session_id,result,created_at) VALUES(1,?,-3,'correct','2026-09-12T10:00:00+02:00')", (tid,))
    client.put(B + f"/sessions/{s['id']}/counts", json={"counts": True})
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE session_id=?", (s["id"],)).fetchone()[0] == 2
        assert c.execute("SELECT COUNT(*) FROM topic_answers WHERE session_id=-3").fetchone()[0] == 3


def test_deleting_a_unit_takes_its_topic_answers_and_resets_the_stage(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Konjugation")["id"]
    s = topic_session(client, patch, tid)
    assert counted(tid)[0] == 3
    version = client.get(B + f"/sessions/{s['id']}").json()["version"]
    r = client.request("DELETE", B + f"/sessions/{s['id']}", json={"version": version})
    assert r.status_code == 200, r.text
    assert counted(tid) == (0, "neu")


# ------------------------------------------------------------ A8 Kontext-Stand

def test_a_photo_read_in_the_background_does_not_throw_the_paid_turn_away(setup):
    client, state, patch = setup
    s = start(client)

    async def meanwhile(*a, **kw):
        # Während des Zugs: Material wird gelesen, eine Aufgabe abgehakt, ein anderer Verlauf läuft weiter.
        with closing(db.webapp_conn()) as c, c:
            c.execute("INSERT INTO materials(account_id,kind,subject_name,title,summary,content_text,created_at,updated_at,hidden,verified,source_label) "
                      "VALUES(1,'worksheet','Deutsch','Blatt','','Frisch gelesen','2026-09-11T15:00:00','2026-09-11T15:00:00',0,1,'')")
            c.execute("INSERT INTO tasks(account_id,title,subject_name,status,source,created_at,updated_at,completed_at) "
                      "VALUES(1,'Deutsch','Deutsch','done','manual','now','now','now')")
            c.execute("INSERT INTO mentor_sessions(account_id,user_id,subject,goal,summary,created_at,updated_at,is_test) "
                      "VALUES(1,1,'Deutsch','Anderes','Neue Zusammenfassung','now','now',0)")
        return json.dumps(reply()), {}, "fake"
    patch.setattr(ai, "complete", meanwhile)
    r = send(client, s)
    assert r.status_code == 200, r.text
    assert r.json()["task"]["prompt"] == TASK["prompt"]


def test_the_stable_version_ignores_background_but_not_the_assignment():
    lessons = [{"id": 1, "date": "2026-09-11", "text": "Adjektive", "rating": 2}]
    base = mc.stable_version("Deutsch", "Ziel", {"task": {"id": 3, "title": "D", "notes": "S. 5", "status": "open"}}, lessons)
    same = mc.stable_version("Deutsch", "Ziel", {"task": {"id": 3, "title": "D", "notes": "S. 5", "status": "done"},
                                                 "loesung": {"volltext": "neu gelesen"}},
                             [{**lessons[0], "rating": 3}, {"id": 2, "date": "2026-09-18", "text": ""}])
    assert base == same
    assert base != mc.stable_version("Deutsch", "Ziel", {"task": {"id": 3, "title": "D", "notes": "S. 6"}}, lessons)
    assert base != mc.stable_version("Deutsch", "Ziel", {"task": {"id": 3, "title": "D", "notes": "S. 5"}},
                                     [{**lessons[0], "text": "Anderes"}])


# ------------------------------------------------------------ A9 Budget

def test_a_small_context_stays_byte_for_byte_the_same():
    ctx = {"messages": [{"role": "user", "text": "x" * 500}] * 4, "lessons": [{"text": "a"}] * 5}
    before = json.dumps(ctx, ensure_ascii=False)
    assert mc.fit_context(ctx, "Anweisung") == [] and json.dumps(ctx, ensure_ascii=False) == before


def test_a_large_context_is_cut_by_priority_under_the_budget():
    ctx = {"messages": [{"role": "assistant", "text": "ä" * 3500} for _ in range(8)],
           "source": {"loesung": {"gedruckte_seite": "Seite " * 900, "volltext": "Seite " * 1300}},
           "eingebunden": [{"id": i, "text": "t" * 3000} for i in range(4)],
           "lessons": [{"id": i, "text": "l" * 1800} for i in range(18)],
           "abfrage": {"bestand": [{"item": f"w{i}", "state": "richtig" if i % 3 else "falsch"} for i in range(60)]}}
    done = mc.fit_context(ctx, "A" * 9000)
    assert 9000 + len(json.dumps(ctx, ensure_ascii=False).encode()) <= mc.CONTEXT_BUDGET
    assert done and done[0].startswith("nachrichten")
    # Die letzten beiden Nachrichten bleiben ganz, der Auftrag des Kindes auch.
    assert len(ctx["messages"][-1]["text"]) == 3500 and ctx["source"]["loesung"]["gedruckte_seite"]


def test_the_turn_sends_a_context_under_the_gateway_limit(setup):
    client, state, patch = setup
    s = start(client)
    with closing(db.webapp_conn()) as c, c:
        for i in range(8):
            c.execute("INSERT INTO mentor_messages(account_id,session_id,request_key,role,text,payload,created_at) VALUES(1,?,?,?,?,'{}','now')",
                      (s["id"], f"k{i}", "assistant" if i % 2 else "user", "Sehr lange Erklärung. " * 180))
    s = client.get(B + f"/sessions/{s['id']}").json()
    seen = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        seen.append(len((instruction + json.dumps(context, ensure_ascii=False)).encode()))
        return json.dumps(reply()), {}, "fake"
    patch.setattr(ai, "complete", complete)
    assert send(client, s).status_code == 200
    assert seen and seen[0] <= 48000


def test_a_long_speaking_test_keeps_its_beginning_and_end():
    from backend import oral_exam
    talk = []
    for i in range(80):
        talk += [{"pruefer": f"Frage {i} " + "x" * 400}, {"kind": f"Antwort {i} " + "y" * 300}]
    ctx = {"gespraech": talk, "messwerte": {"antworten": 80}}
    assert oral_exam.fit_talk(ctx, "I" * 5000)
    assert 5000 + len(json.dumps(ctx, ensure_ascii=False).encode()) <= oral_exam.ASSESS_BUDGET
    assert ctx["gespraech"][0]["pruefer"].startswith("Frage 0") and ctx["gespraech"][-1]["kind"].startswith("Antwort 79")
    assert any("ausgelassen" in t for t in ctx["gespraech"])
    short = {"gespraech": talk[:4]}
    assert not oral_exam.fit_talk(short, "I")


# ------------------------------------------------------------ A10 Sperre

def test_a_second_tap_while_the_turn_runs_is_refused_not_doubled(setup):
    client, state, patch = setup
    s = start(client)
    gate = {"open": False, "calls": 0}

    async def slow(*a, **kw):
        gate["calls"] += 1
        end = time.monotonic() + 3  # ohne Sperre liefe der zweite Tipp hier hinein: nicht ewig warten
        while not gate["open"] and time.monotonic() < end:
            await asyncio.sleep(0.01)
        return json.dumps(reply()), {}, "fake"
    patch.setattr(ai, "complete", slow)
    # Die Sperre in der Datenbank gilt als abgelaufen: Nur die Prozess-Sperre hält den zweiten Tipp auf.
    patch.setattr(m, "PENDING_STALE", -1)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(send, client, s)
        end = time.monotonic() + 5
        while not gate["calls"] and time.monotonic() < end:
            time.sleep(0.01)
        # Anderer Schlüssel, gleicher Stand: wie ein zweiter Tipp nach einem abgebrochenen Aufruf.
        second = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "zweiter_tipp", "version": s["version"], "text": "Nochmal"})
        gate["open"] = True
        assert first.result().status_code == 200
    assert second.status_code == 409 and gate["calls"] == 1
    assert m._TURN_LOCKS == {}


def test_an_old_pending_mark_blocks_until_the_longest_legitimate_turn(setup):
    client, state, patch = setup
    s = start(client)
    old = (datetime.fromisoformat("2026-09-11T15:00:00+02:00") - timedelta(seconds=200)).isoformat()
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_sessions SET pending_key='anderer',pending_since=? WHERE id=?", (old, s["id"]))
    assert send(client, s).status_code == 409
    older = (datetime.fromisoformat("2026-09-11T15:00:00+02:00") - timedelta(seconds=m.PENDING_STALE + 5)).isoformat()
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_sessions SET pending_since=? WHERE id=?", (older, s["id"]))
    mock(patch, [reply()])
    assert send(client, s).status_code == 200


# ------------------------------------------------------------ A11 Buchseiten

def book():
    from test_textbook_pages import seed as seed_book
    return seed_book()


async def test_an_unreachable_page_is_not_tried_again_on_every_turn(env, monkeypatch):
    from backend import textbook_context as ctx
    from backend.textbook_browser import TextbookScanError
    book()
    runs = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        runs.append(list(pages))
        raise TextbookScanError("kaputt (Buch öffnen)", "Buch öffnen")
    monkeypatch.setattr(ctx, "capture_pages", capture)
    _, first = await ctx.homework_page_images(1, "Politik", "Lies S. 34")
    _, second = await ctx.homework_page_images(1, "Politik", "Lies S. 34")
    assert runs == [[34]] and first["status"] == second["status"] == "viewer_error"
    assert second["detail"] == "Vor Kurzem nicht lieferbar"


async def test_pages_out_of_time_are_tried_again_and_blank_ones_not(env, monkeypatch):
    from backend import textbook_context as ctx
    from backend.textbook_browser import CaptureResult, PageShot
    from test_textbook_pages import png
    book()
    runs = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        runs.append(list(pages))
        if len(runs) == 1:
            return CaptureResult(shots=[PageShot(30, png(30))], note="Zeitbudget erreicht")
        return CaptureResult(shots=[PageShot(p, png(p)) for p in pages])
    monkeypatch.setattr(ctx, "capture_pages", capture)
    await ctx.homework_page_images(1, "Politik", "S. 30-31")
    _, context = await ctx.homework_page_images(1, "Politik", "S. 30-31")
    assert runs == [[30, 31], [31]] and context["status"] == "loaded"


async def test_the_chat_does_not_wait_for_a_slow_browser(env, monkeypatch):
    from backend import textbook_context as ctx
    from backend.textbook_browser import CaptureResult, PageShot
    from test_textbook_pages import png
    book()
    monkeypatch.setattr(ctx, "CHAT_WAIT", 0.05)
    release = asyncio.Event()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        await release.wait()
        return CaptureResult(shots=[PageShot(p, png(p)) for p in pages])
    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "S. 30")
    assert parts == [] and context["status"] == "wird_geholt" and context["pending_pages"] == [30]
    assert "missing_pages" not in context and "nächsten Nachricht" in context["hinweis"]
    release.set()
    for _ in range(100):
        if not ctx._FETCHES:
            break
        await asyncio.sleep(0.01)
    parts, context = await ctx.homework_page_images(1, "Politik", "S. 30")
    assert context["status"] == "loaded" and parts


async def test_one_browser_per_book_even_for_other_pages(env, monkeypatch):
    from backend import textbook_context as ctx
    from backend.textbook_browser import CaptureResult, PageShot
    from test_textbook_pages import png
    book()
    monkeypatch.setattr(ctx, "CHAT_WAIT", 0.05)
    release = asyncio.Event()
    runs = []

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        runs.append(list(pages))
        await release.wait()
        return CaptureResult(shots=[PageShot(p, png(p)) for p in pages])
    monkeypatch.setattr(ctx, "capture_pages", capture)
    await ctx.homework_page_images(1, "Politik", "S. 30")
    _, other = await ctx.homework_page_images(1, "Politik", "S. 40")
    assert runs == [[30]] and other["status"] == "wird_geholt"
    release.set()
    for _ in range(100):
        if not ctx._FETCHES:
            break
        await asyncio.sleep(0.01)
    _, again = await ctx.homework_page_images(1, "Politik", "S. 40")
    assert runs == [[30], [40]] and again["status"] == "loaded"


async def test_only_the_pages_sent_are_reported_as_delivered(env, monkeypatch):
    from backend import textbook_context as ctx
    from backend.textbook_browser import CaptureResult, PageShot
    from test_textbook_pages import png
    book()

    async def capture(portal, user, password, title, pages, launch_url=None, survey=False, budget=240.0):
        return CaptureResult(shots=[PageShot(p, png(p)) for p in pages])
    monkeypatch.setattr(ctx, "capture_pages", capture)
    parts, context = await ctx.homework_page_images(1, "Politik", "S. 30-35")
    assert len(parts) == 2 and context["delivered_pages"] == [30, 31, 32, 33]
    assert context["status"] == "partial" and context["missing_pages"] == [34, 35]


# ------------------------------------------------------------ A12 Verfassung und Hilfe

def test_short_answers_are_not_evasive_but_dont_know_is():
    for said in ("12", "3/4", "x=2", "servi", "er", "1,5"):
        assert not m.evasive(said), said
    for said in ("kp", "Weiß nicht", "hä?", "???", "k.a.", "keine Ahnung", "ok"):
        assert m.evasive(said), said


def test_number_answers_do_not_make_the_mentor_think_the_child_is_tired(setup):
    client, state, patch = setup
    s = start(client)
    with closing(db.webapp_conn()) as c:
        for n, text in enumerate(["12", "3/4", "7"]):
            c.execute("INSERT INTO mentor_messages(session_id,account_id,request_key,role,text,payload,created_at) VALUES(?,1,?,'user',?,'{}','now')",
                      (s["id"], f"z{n}", text))
        row = dict(c.execute("SELECT * FROM mentor_sessions WHERE id=?", (s["id"],)).fetchone())
        assert m.condition(c, row, now="2026-09-11T15:00:00+02:00") is None


def test_the_break_offer_after_two_hints_counts_per_task(setup):
    client, state, patch = setup
    s = start(client)
    mock(patch, [reply()])
    s = send(client, s).json()
    mock(patch, [reply(task=None, action="explain")])
    s = send(client, s, kind="hint", text="Tipp bitte").json()
    s = send(client, s, kind="hint", text="Noch ein Tipp").json()
    assert s["messages"][-1]["payload"]["choices"] == ["Anderes Beispiel", "Für heute fertig"]
    # Eine neue Aufgabe beginnt von vorn: kein Zwang mehr zu diesen zwei Knöpfen.
    mock(patch, [reply(task={**TASK, "prompt": "Warum schreibt man viel Neues groß?"}, choices=["Ich probiere es selbst"])])
    s = send(client, s, text="Neue Aufgabe").json()
    mock(patch, [reply(task=None, action="explain", choices=["Noch ein Beispiel"])])
    s = send(client, s, kind="hint", text="Ein Tipp").json()
    assert s["messages"][-1]["payload"]["choices"] == ["Noch ein Beispiel"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT help_count FROM mentor_sessions WHERE id=?", (s["id"],)).fetchone()[0] == 3, "die Einheit zählt weiter (D93)"


# ------------------------------------------------------------ B10 Chips

def test_short_options_do_not_swallow_navigation_chips():
    task = {"solution": "servi", "criteria": "Form", "prompt": "Wähle.", "optionen": [{"text": "er"}, {"text": "12"}, {"text": "sie"}]}
    assert m.safe_choices(["Erst kurz erklären", "Ist es 12?", "Gleich eine Aufgabe"], task) == ["Erst kurz erklären", "Gleich eine Aufgabe"]
    long = {"solution": "x", "criteria": "y", "optionen": [{"text": "etwas Gutes"}]}
    assert m.safe_choices(["Ich nehme etwas Gutes", "Noch ein Beispiel"], long) == ["Noch ein Beispiel"]


# ------------------------------------------------------------ A13 Schultage

def test_holidays_are_no_school_days_beyond_the_timetable(env, monkeypatch):
    from backend import rewards, study_plan
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("CREATE TABLE master_holidays(account_id INTEGER, id INTEGER, name TEXT, longName TEXT, startDate TEXT, endDate TEXT)")
        c.execute("INSERT INTO master_holidays VALUES(1,1,'HF','Herbstferien','2026-10-12','2026-10-23')")
    monkeypatch.setattr(rewards, "_lessons", lambda a, f, l: [
        {"id": 1, "date": "2026-10-01", "start_time": 800, "end_time": 900, "subject_name": "Deutsch", "lstext": ""}])
    monkeypatch.setattr(rewards, "_held", lambda l: True)
    days = study_plan.school_days(1, date(2026, 10, 1), date(2026, 10, 30))
    assert date(2026, 10, 9) in days and date(2026, 10, 26) in days
    assert not any(date(2026, 10, 12) <= d <= date(2026, 10, 23) for d in days)
    lessons = rewards._lessons(1, None, None)
    assert lc._school_days(lessons, date(2026, 10, 1), date(2026, 10, 30), 1) == days


# ------------------------------------------------------------ A14 Geräterolle

def exam_attempt(user):
    from backend.routers import mentor_exams as ex
    tasks = [{**TASK, "prompt": "Aufgabe 1", "points": 2, "minutes": 5}]
    with closing(db.webapp_conn()) as c, c:
        eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) VALUES(1,'Probe','Deutsch',?,?,5,'published','now')",
                        (json.dumps({"topics": ["Nominalisierung"]}), json.dumps(tasks))).lastrowid
    a = ex.start(1, eid, user)
    ex.save(1, a["id"], ex.Answers(version=0, answers={"0": "Antwort"}), user)
    ex.submit(1, a["id"], user)
    return a["id"]


@pytest.mark.parametrize("mode,counts", [("child", 1), (None, 0), ("test", 0)])
def test_the_child_at_the_parents_device_gets_evidence_parents_do_not(setup, mode, counts):
    from backend.routers import mentor_exams as ex
    client, state, patch = setup
    mock(patch, [{"points": 2, "rationale": "Richtig.", "next_step": "Weiter.", "uncertain": False}])
    token = view_mode.current.set(mode)
    try:
        aid = exam_attempt(state.user)
        asyncio.run(ex.grade_next(1, aid, state.user))
    finally:
        view_mode.current.reset(token)
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM mentor_evidence WHERE exam_attempt_id=?", (aid,)).fetchone()[0] == counts


# ------------------------------------------------------------ B12 Schreibrechte

def test_a_read_only_link_cannot_change_exams_courses_or_grades(exam_env):
    client, state, patch, nid, extraction = exam_env
    from backend.auth import CurrentUser
    from backend.routers import courses as courses_router
    client.app.include_router(courses_router.router, prefix="/api")
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Thema")["id"]
    state.user = CurrentUser(4, "test-4", "Test", "parent", False, "pin")  # Elternteil ohne Schreibrecht
    assert client.post("/api/accounts/1/exams/note", json={"exam_key": "k", "note": "x"}).status_code == 403
    assert client.post("/api/accounts/1/exam-progress", json={"exam_key": "k", "grade_points": 12}).status_code == 403
    assert client.delete(f"/api/accounts/1/exams/topics/{tid}").status_code == 403
    assert client.post("/api/accounts/1/courses/hidden", json={"course_key": "x", "hidden": True}).status_code == 403
    assert client.post("/api/accounts/1/exam-overrides", json={"source_key": "s", "decision": "dismissed"}).status_code == 403
    # Das Kind darf weiter, was seine Seite anbietet: Gefühl, Thema ergänzen, Einschätzung.
    child(state)
    assert client.post(f"/api/accounts/1/exams/topics/{tid}/self-view", json={"value": "sicher"}).status_code == 200
    assert client.post("/api/accounts/1/exam-progress", json={"exam_key": "k", "learn_state": 2}).status_code == 200
    assert client.post("/api/accounts/1/exams/topics", json={"exam_key": "k", "subject": "Latein", "title": "Neu"}).status_code == 201
    assert client.delete(f"/api/accounts/1/exams/topics/{tid}").status_code == 403


# ------------------------------------------------------------ Zeitzone

def test_a_homework_ticked_late_in_the_evening_counts_for_that_berlin_day(env):
    with closing(db.webapp_conn()) as c, c:
        for stamp in ("2026-09-11T21:30:00+00:00",   # 23:30 in Berlin, 11.09.
                      "2026-09-10T22:30:00+00:00",   # 00:30 in Berlin, 11.09.
                      "2026-09-11T22:30:00+00:00"):  # 00:30 in Berlin, 12.09.
            c.execute("INSERT INTO tasks(account_id,title,status,source,estimated_minutes,created_at,updated_at,completed_at) "
                      "VALUES(1,'HA','done','manual',10,'now','now',?)", (stamp,))
        assert sorted(lp.done_minutes(c, 1, date(2026, 9, 11))) == [10, 10]
        assert lp.usage(c, 1, date(2026, 9, 11))["homework"] == 20
    assert lp.local_day("2026-09-11") == date(2026, 9, 11) and lp.local_day("now") is None


def test_both_photo_stores_share_one_quota():
    from backend.routers import mentor_exams, practice as practice_router
    assert practice_router.PHOTO_QUOTA is mentor_exams.PHOTO_QUOTA == 200 * 1024 * 1024


# ------------------------------------------------------------ Leistung

def test_reading_the_plan_writes_nothing_when_the_skill_state_is_current(setup):
    client, state, patch = setup
    mock(patch, [reply(), reply(task={**TASK, "prompt": "Zweite Aufgabe"}, assessment={"result": "correct", "rationale": "Gut."})])
    s = send(client, start(client)).json()
    send(client, s, kind="answer", text="Nominalisiert.")
    client.get(B)
    with closing(db.webapp_conn()) as c:
        # data_version ändert sich, sobald eine andere Verbindung etwas festschreibt.
        before = c.execute("PRAGMA data_version").fetchone()[0]
        lp.catalogue(1)
        assert c.execute("PRAGMA data_version").fetchone()[0] == before, "Lesen schreibt nichts"
    with closing(db.webapp_conn()) as c:
        skill = c.execute("SELECT skill_id FROM learning_skill_state").fetchone()[0]
        c.execute("UPDATE learning_skill_state SET label='veraltet' WHERE skill_id=?", (skill,))
        c.execute("DELETE FROM mentor_reviews")
        lp.catalogue(1)
        assert c.execute("SELECT label FROM learning_skill_state WHERE skill_id=?", (skill,)).fetchone()[0] != "veraltet"
        assert c.execute("SELECT COUNT(*) FROM mentor_reviews").fetchone()[0] == 1, "abweichender Stand wird wie bisher aufgefrischt"


def _sure_moments_before(answers):
    cells, ready_at = {}, None
    for i, a in enumerate(answers):
        row = practice.row_of(answers[: i + 1])
        for k, c in row["cells"].items():
            if k not in cells and practice.is_sure(c) and not c.get("implied"):
                cells[k] = a["created_at"]
        if ready_at is None and row["ready"]:
            ready_at = a["created_at"]
    return cells, ready_at


def test_sure_moments_match_the_old_quadratic_count():
    rnd = random.Random(7)
    for trial in range(60):
        answers = []
        for i in range(rnd.randint(0, 40)):
            answers.append({"created_at": f"2026-09-{1 + i // 3:02d}T1{i % 10}:00:00", "afb": rnd.choice([1, 2, 3, None]),
                            "help_used": rnd.random() < .2, "result": rnd.choice(["correct", "partial", "incorrect", "uncertain"]),
                            "points": rnd.choice([None, 0, 2, 4]), "max_points": 4,
                            "paper_format": rnd.choice([None, "einstieg", "probe"])})
        assert lc.sure_moments(answers) == _sure_moments_before(answers), trial
