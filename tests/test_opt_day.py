"""Robustheit von Erinnerungen, Belohnungen, Rückmeldungen und Papiertest (opt_day).

Keine Regel wird rückwirkend angewandt: gespeicherte Ereignisse, Tage und
Abzeichen bleiben, wie sie sind; nur neue Handlungen folgen den neuen Regeln.
"""
import json
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, child  # noqa: F401
from test_mentor import setup  # noqa: F401
from test_rewards import KID, PARENT, START, at, finish, kinds, school, world  # noqa: F401
from backend import db, day_close, reminders as r, rewards


def _q(sql, *params):
    with closing(db.webapp_conn()) as c:
        return c.execute(sql, params).fetchall()


def _events(kind):
    return [row[0] for row in _q("SELECT ref FROM reward_events WHERE kind=?", kind)]


# ------------------------------------------------------------ Tagesabschluss

def test_photos_do_not_keep_the_evening_open(env):
    """A4: Der Abschluss zählt Aufgaben, Tasche, Rückmeldungen, keine Heftseiten."""
    now = datetime(2026, 9, 14, 18, 0, tzinfo=r.ZONE)
    got = day_close.record_if_clear(1, "2026-09-14", dict(homework=0, material=0, feedback=0, photos=3), now)
    assert got and got["closed_by"] == day_close.BY_WORK
    assert day_close.record_if_clear(2, "2026-09-14", dict(homework=1, material=0, feedback=0, photos=0), now) is None


def test_every_account_gets_its_day_closed_and_only_switched_on_messages(env, monkeypatch):
    """A3: Tagesabschluss für jedes Konto, jede Mitteilung an ihrem eigenen
    Schalter. Ohne Abend-Erinnerung keine Abend-Mitteilung."""
    from backend import app_notify
    sent = []
    monkeypatch.setattr(app_notify, "own_panel", lambda: "/x")
    monkeypatch.setattr(app_notify, "send", lambda service, title, message, url: sent.append((service, title)) or True)
    app_notify.set_targets(1, ["mobile_app_kind_1"])
    app_notify.set_targets(2, ["mobile_app_kind_2"])
    with closing(db.webapp_conn()) as c:
        # Konto 1: Abend aus, Morgen an. Konto 2: keine Zeile, alles aus.
        c.execute("INSERT INTO reminder_settings(account_id,enabled,remind_at,morning_enabled,morning_at) "
                  "VALUES(1,0,'18:00',1,'06:45')")
    open_counts = dict(homework=1, material=1, feedback=0, photos=0)
    monkeypatch.setattr(r, "snapshot", lambda *a, **k: open_counts)
    monkeypatch.setattr(r, "packing_plan", lambda account, day: ([{"key": "subject:ma"}], "x", []))

    evening = datetime(2026, 9, 14, 18, 0, tzinfo=r.ZONE)
    r.run_once(evening)
    assert sent == [], "Abend-Erinnerung aus: keine Abend-Mitteilung"

    morning = datetime(2026, 9, 15, 6, 50, tzinfo=r.ZONE)
    r.run_once(morning)
    assert sent == [("mobile_app_kind_1", "Vor dem Aufbruch")], "Morgen an, Abend aus: nur die Morgenmitteilung"

    # Alles erledigt: Beide Konten schließen den Abend ab, auch ohne Einstellungen.
    open_counts.update(homework=0, material=0)
    r.run_once(datetime(2026, 9, 15, 19, 0, tzinfo=r.ZONE))
    assert day_close.closure(1, "2026-09-15") and day_close.closure(2, "2026-09-15")


# ------------------------------------------------ Geschafft ohne Kind-Handlung

def test_the_minute_loop_counts_a_day_the_parent_finished(world):
    """A5: Das Kind hat heute etwas getan, die Eltern erledigen den letzten Punkt
    und niemand öffnet die App: Die Minutenschleife trägt den Tag ein."""
    mon, tue = START, START + timedelta(days=1)
    school(world, mon, 1); school(world, tue, 2)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO tasks(id,account_id,title,task_type,status,due_date,source,created_at,updated_at) "
                  "VALUES(9,1,'Mathe','homework','open',?,'manual','t','t')", (tue.isoformat(),))
    finish(mon, 1, tue)
    rewards.note(1, "feedback", 1, KID, at(mon, 14))
    assert kinds() == {}
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE tasks SET status='done'")  # die Eltern
    r._REWARD_CHECKED.clear()
    assert r.check_rewards(1, at(mon, 16, 10))
    assert kinds() == {mon.isoformat(): "full"}
    assert not r.check_rewards(1, at(mon, 16, 12)), "höchstens alle fünf Minuten"


def test_the_minute_loop_awards_nothing_without_the_child(world):
    mon, tue = START, START + timedelta(days=1)
    school(world, mon, 1); school(world, tue, 2)
    finish(mon, 1, tue)
    r._REWARD_CHECKED.clear()
    assert not r.check_rewards(1, at(mon, 16))
    rewards.note(1, "feedback", 1, PARENT, at(mon, 15))  # Eltern zählen nicht
    r._REWARD_CHECKED.clear()
    r.check_rewards(1, at(mon, 16, 30))
    assert kinds() == {}


# ------------------------------------------------ Ausgefallene Quelle (A6)

def test_an_unreadable_timetable_takes_nothing_back(world):
    """Liest der Stundenplan nicht, sind Serie und Tage unbekannt, nicht null."""
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_badges(account_id,badge,level,reached_at,celebrated_at) VALUES(1,'geschafft',1,'t','t')")
        c.execute("INSERT INTO reward_badges(account_id,badge,level,reached_at,celebrated_at) VALUES(1,'dranbleiber',1,'t','t')")
    # Kein Stundenplan in der Welt; die echte Quelle hat keine Tabelle lessons.
    s = rewards.summary(1, at(START + timedelta(days=3), 18))
    level = {b["key"]: b["level"] for b in s["badges"]}
    assert level["geschafft"] == 1 and level["dranbleiber"] == 1
    assert {row[0] for row in _q("SELECT badge FROM reward_badges")} == {"geschafft", "dranbleiber"}
    assert not [p for p in s["celebrate"] if p["badge"] in ("geschafft", "dranbleiber")]


def test_unreadable_learning_counts_take_nothing_back(world, monkeypatch):
    from backend import reward_extras
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_badges(account_id,badge,level,reached_at,celebrated_at) VALUES(1,'probearbeit',1,'t','t')")

    def broken(c, account_id):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(reward_extras, "_answers", broken)
    assert reward_extras.counts(1, START, START)["probearbeit"] is None
    s = rewards.summary(1, at(START, 18))
    assert next(b for b in s["badges"] if b["key"] == "probearbeit")["level"] == 1
    assert _q("SELECT COUNT(*) FROM reward_badges WHERE badge='probearbeit'")[0][0] == 1


def test_the_next_school_day_after_long_holidays(world):
    """Nachholen nach langen Ferien: die weite Suche findet den ersten Schultag."""
    last = START
    first_after = START + timedelta(days=45)
    school(world, last, 1); school(world, first_after, 2)
    assert rewards._next_school_day(1, last) is None, "was am Tag selbst gilt, bleibt bei drei Wochen"
    assert rewards._next_school_day(1, last, far=True) == first_after


# ------------------------------------------------------- Taschen (8a)

def test_a_bag_counts_only_for_today_or_the_next_school_day(monkeypatch):
    from backend.routers import packing as routes
    today = date(2026, 9, 14)
    monkeypatch.setattr(rewards, "_next_school_day", lambda account, after, far=False: date(2026, 9, 15))
    assert routes.bag_counts(1, today, today)
    assert routes.bag_counts(1, date(2026, 9, 15), today)
    assert not routes.bag_counts(1, date(2026, 9, 16), today)
    assert not routes.bag_counts(1, date(2026, 9, 11), today)


def test_packing_ahead_works_but_earns_no_bag(env):
    from test_packing import DAY, install, mark, url
    client, _, patch, _ = install(env)
    patch.setattr(rewards, "_next_school_day", lambda account, after, far=False: DAY + timedelta(days=1))
    for day in (DAY + timedelta(days=5), DAY):
        data = client.get(url(day)).json()
        for item in data["items"]:
            assert mark(client, data, item).status_code == 200
        assert client.get(url(day)).json()["status"] == "packed"
    assert _events("bag") == [DAY.isoformat()], "nur die Tasche für heute zählt"


# ------------------------------------------------------- Aufgaben (8b, 8e)

def test_deleting_an_own_task_takes_its_note_back_unless_a_badge_needs_it(env):
    from backend.routers import tasks as task_routes
    client, state, _ = env
    client.app.include_router(task_routes.router, prefix="/api")
    child(state)
    ids = [client.post("/api/accounts/1/tasks", json={"title": f"Brief {i}", "task_type": "reminder"}).json()["id"]
           for i in range(6)]
    assert len(_events("note")) == 6
    assert client.delete(f"/api/tasks/{ids[0]}").status_code == 200
    assert len(_events("note")) == 5, "Anlegen und Löschen zählt nicht"
    # Bronze bei 5 ist erreicht: Das Ereignis wird gebraucht und bleibt.
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_badges(account_id,badge,level,reached_at,celebrated_at) VALUES(1,'notiert',1,'t','t')")
    assert client.delete(f"/api/tasks/{ids[1]}").status_code == 200
    assert len(_events("note")) == 5
    assert _q("SELECT COUNT(*) FROM reward_badges WHERE badge='notiert'")[0][0] == 1


def test_only_parents_skip_a_task_and_done_still_counts_for_the_child(env):
    from backend.routers import tasks as task_routes
    client, state, _ = env
    client.app.include_router(task_routes.router, prefix="/api")
    child(state)
    tid = client.post("/api/accounts/1/tasks", json={"title": "Mathe", "due_date": "2026-09-15"}).json()["id"]
    assert client.patch(f"/api/tasks/{tid}", json={"status": "skipped"}).status_code == 403
    assert client.patch(f"/api/tasks/{tid}", json={"status": "done"}).status_code == 200
    assert _events("task") == [str(tid)], "die Belohnung läuft nach der Antwort und kommt an"
    from backend.auth import CurrentUser
    state.user = CurrentUser(1, "test-1", "Test", "parent", False, "pin")
    tid2 = client.post("/api/accounts/1/tasks", json={"title": "Sport"}).json()["id"]
    assert client.patch(f"/api/tasks/{tid2}", json={"status": "skipped"}).status_code == 200


# ------------------------------------------------------- Rückmeldungen (8c, 12)

def _lessons_table(days):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY, account_id INTEGER, untis_period_id INTEGER, "
                  "date TEXT, start_time INTEGER, end_time INTEGER, was_absent INTEGER, code TEXT, subject_name TEXT)")
        for lid, day in days.items():
            c.execute("INSERT INTO lessons VALUES(?,1,?,?,800,845,0,NULL,'Mathematik')", (lid, 100 + lid, day.isoformat()))


def test_future_lessons_are_saved_but_earn_nothing_and_notes_survive_a_rating(env):
    from backend.learning import today_local
    from backend.routers import checkins
    client, state, _ = env
    client.app.include_router(checkins.router, prefix="/api")
    child(state)
    _lessons_table({1: today_local() - timedelta(days=1), 2: today_local() + timedelta(days=1)})
    post = lambda lid, **body: client.post(f"/api/accounts/1/lessons/{lid}/checkin", json=body)
    assert post(2, rating=3).json()["rating"] == 3
    assert _events("feedback") == [], "eine Stunde in der Zukunft zählt nicht"
    assert post(1, note="Heft mitbringen").json()["note"] == "Heft mitbringen"
    assert post(1, rating=3).json()["note"] == "Heft mitbringen", "Bewertung ohne Notiz lässt die Notiz stehen"
    assert post(1, rating=2, note=None).json()["note"] == "Heft mitbringen"
    assert _events("feedback") == ["1"]
    got = post(1, rating=None, note=None).json()
    assert got["note"] is None and got["rating"] == 2, "Notiz bewusst gelöscht, Bewertung bleibt"


# ------------------------------------------------------- Vokabeln (8d)

def test_gave_up_is_no_practised_word_and_one_event_per_word_and_day(setup):
    from test_vocab import WORDS, V, seed_page
    from backend import vocab, vocab_pensum
    from backend.routers import vocab as vocab_router
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    child(state)
    mid = seed_page()
    with closing(db.webapp_conn()) as c, c:
        for pos, w in enumerate(WORDS["words"][:2]):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) "
                      "VALUES(1,'LATEIN',?,'Begleitband',10,'Lektion 1',?,?,?,?,'now')",
                      (mid, pos, w["foreign_word"], vocab.plain(w["foreign_word"]), json.dumps(w["meanings"])))
        ids = [row[0] for row in c.execute("SELECT id FROM vocab_words ORDER BY position")]
    ask = lambda wid, **body: client.post(V + "/attempts", json={"word_id": wid, "stage": 1, "direction": "from", **body})
    assert ask(ids[0], gave_up=True).json()["result"] == "incorrect"
    assert _events("vocab") == [], "„Weiß ich nicht“ zählt nicht für Wortschatz"
    today = vocab.now_iso()[:10]
    day = date.fromisoformat(today)
    assert _q("SELECT COUNT(*) FROM reward_activity WHERE day=?", today)[0][0] == 1, "aber als Handlung des Tages"
    # Fürs Pensum ist es ein falsch geübtes Wort (D215), für Extrameile und Abzeichen nicht.
    assert vocab_pensum.practiced(1, day) == {ids[0]}
    assert vocab_pensum.practiced(1, day, gave_up=False) == set()
    assert ask(ids[1], answer="sein").json()["result"] == "correct"
    assert ask(ids[1], answer="sich befinden").json()["result"] == "correct"
    assert _events("vocab") == [f"{ids[1]}:{today}"], "ein Ereignis je Wort und Tag"
    assert ask(ids[0], answer="Schau!").json()["result"] == "correct"
    assert vocab_pensum.practiced(1, day) == set(ids), "nach dem Aufgeben noch einmal beantwortet: geübt"


def test_a_blank_on_the_paper_test_still_counts_as_practised(env):
    from backend import vocab_pensum
    from test_vocab_pensum import words
    words(3)
    one, two, three = (row[0] for row in _q("SELECT id FROM vocab_words ORDER BY id"))
    with closing(db.webapp_conn()) as c, c:
        for wid, source, answer in ((one, "paper", ""), (two, None, ""), (three, None, "falsch")):
            c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,created_at,user_id,source) "
                      "VALUES(1,?,1,'from',?,'incorrect','2026-09-14T16:00:00+02:00',2,?)", (wid, answer, source))
    assert vocab_pensum.practiced(1, date(2026, 9, 14)) == {one, two, three}, "fürs Pensum zählt auch „Weiß ich nicht“ (D215)"
    assert vocab_pensum.practiced(1, date(2026, 9, 14), gave_up=False) == {one, three}


# ------------------------------------------------------- Papiertest (9)

def test_a_grading_that_a_restart_cut_off_expires(setup):
    from test_vocab_pensum import image, mock, words, EN
    from backend.routers import vocab_daily
    from backend.learning import now_iso
    client, state, patch = setup
    client.app.include_router(vocab_daily.router, prefix="/api")
    words(12)
    child(state)
    p = client.post("/api/accounts/1/vocab/papers", json={"subject": EN, "unit": "Unit 3", "count": 10}).json()
    base = f"/api/accounts/1/vocab/papers/{p['id']}"
    client.post(base + "/pages", files={"file": ("p.jpg", image(), "image/jpeg")})
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE vocab_papers SET status='grading', grading_started_at=? WHERE id=?", (now_iso(), p["id"]))
    assert client.post(base + "/grade").status_code == 409, "eine laufende Auswertung sperrt"
    old = (datetime.fromisoformat(now_iso()) - timedelta(minutes=11)).isoformat()
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE vocab_papers SET grading_started_at=? WHERE id=?", (old, p["id"]))
    mock(patch, lambda ctx: {"words": [{"nr": w["nr"], "verdict": "richtig", "read": "x"} for w in ctx["woerter"]]}, [])
    r = client.post(base + "/grade")
    assert r.status_code == 200 and r.json()["status"] == "graded"
    assert _q("SELECT COUNT(*) FROM vocab_attempts")[0][0] == 10


def test_grading_status_helpers():
    from backend.routers import vocab_daily as vd
    from backend.learning import now_iso
    fresh = {"status": "grading", "grading_started_at": now_iso()}
    stale = {"status": "grading", "grading_started_at": "2026-01-01T10:00:00+01:00"}
    legacy = {"status": "grading", "grading_started_at": None}
    assert vd._grading_live(fresh) and vd._status(fresh) == "grading"
    assert not vd._grading_live(stale) and vd._status(stale) == "active"
    assert vd._status(legacy) == "active"
    assert vd._status({"status": "graded", "grading_started_at": None}) == "graded"


# ------------------------------------------------------- Zeitbasis (10)

def test_completed_at_is_read_as_german_day(env):
    from backend import week_review, week_rolling
    # Montag 14.09. um 01:30 deutscher Zeit ist in UTC noch Sonntag.
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO tasks(account_id,title,status,source,created_at,updated_at,completed_at) "
                  "VALUES(1,'Nachts','done','manual','t','t','2026-09-13T23:30:00+00:00')")
        c.execute("INSERT INTO tasks(account_id,title,status,source,created_at,updated_at,completed_at) "
                  "VALUES(1,'Abends','done','manual','t','t','2026-09-13T20:00:00+00:00')")
    assert week_review.local_day("2026-09-13T23:30:00+00:00") == "2026-09-14"
    assert week_review.local_day("2026-09-13T23:30:00") == "2026-09-13", "ohne Zone: deutsche Zeit"
    with closing(db.webapp_conn()) as c:
        assert week_review.done_between(c, 1, "2026-09-14", "2026-09-20") == 1
        assert week_review.done_between(c, 1, "2026-09-07", "2026-09-13") == 1
    assert week_rolling.review(1, "2026-09-14", "2026-09-20", [])["homework_done"] == 1


def test_a_bad_week_start_is_a_400(env):
    from backend.routers import week
    client, _, _ = env
    client.app.include_router(week.router, prefix="/api")
    assert client.get("/api/accounts/1/week", params={"start": "kaputt"}).status_code == 400
