"""Die Startseite der Eltern (D166): Status nach festen Regeln, was jetzt offen
ist, die Arbeiten chronologisch mit Balken, und jeder Baustein führt zum Kind."""
import sqlite3
from contextlib import closing
from datetime import date, datetime

from test_learning import env  # noqa: F401
from test_day_close import LESSON_COLUMNS
from backend import db, family_board as fb
from backend import lernstand, sources

TODAY = date(2026, 9, 24)   # Donnerstag
MORNING = datetime(2026, 9, 24, 10, 0)
EVENING = datetime(2026, 9, 24, 19, 0)


def task(title, due):
    return {"id": hash(title) % 1000, "title": title, "due_date": due}


def quiet(patch, bag=None, feedback=None, retakes=(), bag_day=("2026-09-25", "after")):
    patch.setattr(fb, "bag_target", lambda a, t, n: bag_day if bag else (None, "school"))
    if bag:
        from backend import packing
        patch.setattr(packing, "packing_plan", lambda a, d: ([{"key": k} for k in range(bag[1])], "x", {}))
        patch.setattr(packing, "view", lambda *a: {"items": [{}] * bag[1], "confirmed_count": bag[0]})
    patch.setattr(fb, "feedback", lambda a, t, n: feedback or {"earlier": 0, "today": 0, "today_total": 6, "total": 6})
    from backend import materials
    patch.setattr(materials, "retakes", lambda a: list(retakes))


def exam(days, missing=0, topics=2, practiced=0, subject="Mathematik"):
    return {"subject_name": subject, "days_until": days, "missing": missing, "topics": topics, "practiced": practiced}


def test_the_status_follows_fixed_rules():
    assert fb.level([], [])["label"] == "Im Griff"
    overdue = [{"tone": "bad", "title": "1 Aufgabe überfällig"}]
    assert fb.level(overdue, [])["level"] == "bad"
    # Material fehlt für eine Arbeit in 7 Tagen: eingreifen; in 8 Tagen noch nicht.
    assert fb.level([], [exam(7, missing=2, practiced=1)])["level"] == "bad"
    assert fb.level([], [exam(8, missing=2, practiced=1)])["level"] == "good"
    # In 14 Tagen eine Arbeit und nichts geübt: nachsteuern. Ohne bekannte Themen
    # lässt sich das nicht sagen.
    assert fb.level([], [exam(14)])["level"] == "warn"
    assert fb.level([], [exam(15)])["level"] == "good"
    assert fb.level([], [exam(10, topics=0)])["level"] == "good"
    assert fb.level([{"tone": "info", "title": "x"}], [])["level"] == "good"
    assert fb.level([{"tone": "warn", "title": "x"}], [])["reasons"] == ["x"]


def test_what_is_due_tomorrow_only_counts_from_the_evening(env, monkeypatch):
    quiet(monkeypatch, bag=(1, 2))
    tasks = [task("Brüche", "2026-09-25")]
    rows, ok = fb.acute(1, tasks, TODAY, MORNING, evening=False)
    assert {r["key"]: r["tone"] for r in rows} == {"due": "info", "bag": "info"}
    rows, ok = fb.acute(1, tasks, TODAY, EVENING, evening=True)
    assert {r["key"]: r["tone"] for r in rows} == {"due": "warn", "bag": "warn"}
    assert "6/6 Stunden bewertet" in ok
    due = next(r for r in rows if r["key"] == "due")
    assert due["go"] == {"page": "today", "args": [], "section": "aufgaben"}
    # Fällig heute und noch offen ist schon vor dem Abend dran; überfällig ist rot.
    rows, _ = fb.acute(1, [task("Lesen", "2026-09-24"), task("Vokabeln", "2026-09-22")], TODAY, MORNING, evening=False)
    assert {r["key"]: r["tone"] for r in rows} == {"overdue": "bad", "due": "warn", "bag": "info"}


def lessons(rows):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f"CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})")
        c.executemany("INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) "
                      "VALUES(?,1,?,?,?,'Mathematik',?,0)", rows)


def test_the_bag_follows_the_school_day(env):
    """Vor dem Unterricht die Tasche für heute, gepackt am Vorabend; während der
    Schulzeit keine; nach Schulschluss die für den nächsten Schultag."""
    lessons([(1, "2026-09-25", 800, 845, None), (2, "2026-09-25", 1230, 1315, None),
             (3, "2026-09-28", 800, 845, None), (4, "2026-09-26", 900, 945, "cancelled")])
    friday = date(2026, 9, 25)
    assert fb.bag_target(1, friday, datetime(2026, 9, 25, 0, 8)) == ("2026-09-25", "before")
    assert fb.bag_target(1, friday, datetime(2026, 9, 25, 7, 59)) == ("2026-09-25", "before")
    assert fb.bag_target(1, friday, datetime(2026, 9, 25, 10, 0)) == (None, "school")
    assert fb.bag_target(1, friday, datetime(2026, 9, 25, 13, 15)) == ("2026-09-28", "after")
    # Samstag ist frei (die eine Stunde fällt aus): die Tasche für Montag.
    assert fb.bag_target(1, date(2026, 9, 26), datetime(2026, 9, 26, 8, 0)) == ("2026-09-28", "after")


def test_before_school_an_unpacked_bag_is_due_and_monday_waits_until_sunday(env, monkeypatch):
    quiet(monkeypatch, bag=(1, 3), bag_day=("2026-09-24", "before"))
    rows, _ = fb.acute(1, [], TODAY, datetime(2026, 9, 24, 7, 0), evening=False)
    assert [(r["tone"], r["title"]) for r in rows] == [("warn", "Tasche für heute: 1 von 3 Fächern")]
    quiet(monkeypatch, bag=(3, 3), bag_day=("2026-09-24", "before"))
    assert "Tasche für heute gepackt" in fb.acute(1, [], TODAY, MORNING, evening=False)[1]
    # Freitagabend, Tasche für Montag: sichtbar, aber noch keine Mahnung.
    friday = date(2026, 9, 25)
    quiet(monkeypatch, bag=(0, 3), bag_day=("2026-09-28", "after"))
    rows, _ = fb.acute(1, [], friday, datetime(2026, 9, 25, 19, 0), evening=True)
    assert [(r["tone"], r["title"]) for r in rows] == [("info", "Tasche für Mo 28.09.: 0 von 3 Fächern")]
    # Während der Schulzeit steht zur Tasche nichts da.
    quiet(monkeypatch, bag=None)
    rows, ok = fb.acute(1, [], TODAY, MORNING, evening=False)
    assert not [r for r in rows if r["key"] == "bag"] and not [o for o in ok if "Tasche" in o]


def test_everything_done_is_one_line(env, monkeypatch):
    quiet(monkeypatch, bag=(2, 2))
    rows, ok = fb.acute(1, [], TODAY, EVENING, evening=True)
    assert rows == []
    assert ok == ["Aufgaben bis morgen erledigt", "Tasche für Fr gepackt", "6/6 Stunden bewertet"]


def test_retakes_and_feedback_lead_to_the_right_section(env, monkeypatch):
    quiet(monkeypatch, feedback={"earlier": 2, "today": 0, "today_total": 3, "total": 9},
          retakes=[{"title": "Zerlegen", "reason": "unscharf"}])
    rows, _ = fb.acute(1, [], TODAY, MORNING, evening=False)
    by = {r["key"]: r for r in rows}
    # Neu fotografieren ist Elternsache und führt nach „Erledigen“, nicht ins Mitlesen (D183).
    assert by["retake"]["go"] == {"page": "erledigen", "args": [], "section": None, "parent": True}
    # Ältere Stunden ohne Rückmeldung stehen in der Woche, nicht auf „Heute“.
    assert by["feedback"]["tone"] == "warn" and by["feedback"]["go"]["page"] == "week"


def test_only_ended_lessons_of_today_ask_for_feedback(env):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f"CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})")
        c.executemany("INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) "
                      "VALUES(?,1,?,?,?,'Mathematik',?,0)",
                      [(1, "2026-09-23", 800, 845, None), (2, "2026-09-24", 800, 845, None),
                       (3, "2026-09-24", 1300, 1345, None), (4, "2026-09-24", 900, 945, "cancelled")])
    assert fb.feedback(1, TODAY, MORNING) == {"earlier": 1, "today": 1, "today_total": 1, "total": 2}
    assert fb.feedback(1, TODAY, EVENING)["today"] == 2


def test_exams_stand_in_order_with_their_bar_and_a_jump_to_the_card(env, monkeypatch):
    topics = {"cal:m": [{"stage": "gefestigt"}, {"stage": "sitzt"}, {"stage": "wackelt"}, {"stage": "neu"},
                        {"stage": "neu", "stale": True}],
              "cal:e": [{"stage": "angefangen"}]}
    monkeypatch.setattr(lernstand, "topics_for", lambda a, key, s, with_material=True: topics.get(key, []))
    monkeypatch.setattr(lernstand, "ensure_assumed_topics", lambda *a: None)
    monkeypatch.setattr(sources, "exam_sources", lambda a, s, since, until: {"missing": 2 if s == "Englisch" else 0,
                                                                             "pending": 0, "ready": 3})
    upcoming = [{"exam_key": "cal:e", "subject_name": "Englisch", "date": "2026-10-01", "title": "Sprechprüfung Englisch"},
                {"exam_key": "cal:m", "subject_name": "Mathematik", "date": "2026-09-28", "title": "Mathearbeit Nr. 1"},
                {"exam_key": "cal:p", "subject_name": "Politik", "date": "2026-10-29", "title": "Klassenarbeit Powi"},
                {"exam_key": "cal:x", "subject_name": "Physik", "date": "2027-02-01", "title": "Physik"}]
    near, later = fb.exam_rows(1, upcoming, upcoming, TODAY)
    assert [x["subject_name"] for x in near] == ["Mathematik", "Englisch"]
    math, english = near
    assert math["stages"] == {"sitzt": 2, "wackelt": 1, "angefangen": 0, "neu": 1}
    assert (math["topics"], math["practiced"], math["material_ok"], math["days_until"]) == (4, 3, True, 4)
    assert math["go"] == {"page": "klausuren", "args": [], "section": "arbeit-cal:m"}
    assert (english["kind"], english["missing"], english["material_ok"]) == ("Sprechprüfung", 2, False)
    # Später: nur bis 90 Tage, ohne Balken, mit dem, was fehlt.
    assert [x["subject_name"] for x in later] == ["Politik"] and later[0]["topics"] == 0
    assert fb.level([], near)["level"] == "bad"


def test_exam_kinds_and_day_labels():
    assert fb.exam_kind("Schriftliche Lernkontrolle Musik (Klausur)") == "Lernkontrolle"
    assert fb.exam_kind("Vergleichsarbeit 6. Chemie (Klausur)") == "Vergleichsarbeit"
    assert fb.exam_kind("Mathearbeit Nr. 1 (Klausur)") == "Arbeit"
    assert fb.day_label("2026-09-28") == "Mo 28.09."


def test_the_late_hint_only_comes_from_the_childs_own_login(env, monkeypatch):
    from backend import usage_report
    monkeypatch.setattr(usage_report, "week", lambda a, t: {"late": []})
    support = [{"subject_id": 8, "subject_name": "Mathematik", "subject_short": "M", "hard_count": 4, "total_count": 10}]
    rows = fb.watch(1, support, TODAY)
    assert [r["title"] for r in rows] == ["Mathematik fällt schwer"]
    assert rows[0]["go"] == {"page": "subject", "args": ["8"], "section": None}
    monkeypatch.setattr(usage_report, "week", lambda a, t: {"late": [{"day": "23.09.", "times": ["22:40"]}]})
    assert fb.watch(1, [], TODAY)[0]["title"] == "Spät auf dem eigenen Gerät"


def test_the_dashboard_brings_the_board_in_one_request(env, monkeypatch):
    client, state, patch = env
    from backend.routers import dashboard

    async def exams(*a, **kw):
        return {"exams": []}
    monkeypatch.setattr(dashboard, "resolve_exams", exams)
    monkeypatch.setattr(dashboard, "account_subjects", lambda a: [])
    quiet(monkeypatch)
    client.app.include_router(dashboard.router, prefix="/api")
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO tasks(account_id,title,task_type,status,source,due_date,created_at,updated_at) "
                  "VALUES(1,'Brüche','homework','open','manual','2020-01-01','now','now')")
    body = client.get("/api/dashboard").json()
    kid = next(k for k in body["kids"] if k["account_id"] == 1)
    assert kid["board"]["status"]["label"] == "Eingreifen"
    assert kid["board"]["acute"][0]["key"] == "overdue"
    assert "plan" not in kid


def test_the_today_page_skips_a_day_where_everything_is_cancelled(env, monkeypatch):
    client, state, patch = env
    from datetime import timedelta
    from backend.routers import today as today_routes
    from backend.learning import today_local
    first, second = (today_local() + timedelta(days=1)).isoformat(), (today_local() + timedelta(days=2)).isoformat()
    lesson = lambda day, cancelled: {"id": 1, "date": day, "start_time": 800, "end_time": 845,
                                     "is_cancelled": cancelled, "was_absent": False}
    monkeypatch.setattr(today_routes, "lessons_for_date", lambda c, a, d: {
        first: [lesson(first, True)], second: [lesson(second, False)]}.get(d, []))
    monkeypatch.setattr(today_routes, "upcoming_exams", lambda *a, **kw: [])
    monkeypatch.setattr(today_routes, "hidden_keys", lambda a: set())
    client.app.include_router(today_routes.router, prefix="/api")
    assert client.get("/api/accounts/1/today").json()["next"]["date"] == second


def test_the_schedule_shows_today_and_the_next_school_day(env):
    """Heute bleibt bis Mitternacht stehen, dazu der nächste Schultag; am
    Wochenende die nächsten zwei (D170)."""
    lessons([(11, "2026-09-25", 750, 835, None), (12, "2026-09-25", 945, 1030, None),
             (13, "2026-09-25", 1135, 1220, "cancelled"), (14, "2026-09-25", 1225, 1310, "cancelled"),
             (15, "2026-09-28", 750, 835, None), (16, "2026-09-29", 750, 835, "cancelled")])
    friday = date(2026, 9, 25)
    days = fb.schedule(1, friday, datetime(2026, 9, 25, 14, 0))
    assert [d["label"] for d in days] == ["Heute", "Mo 28.09."]
    today = days[0]
    assert (today["start"], today["end"], today["planned_end"]) == ("07:50", "10:30", "13:10")
    assert today["early_end"] and today["headline"] == "früher Schluss 10:30 statt 13:10"
    assert today["notes"] == ["Mathematik 11:35–13:10 fällt aus"]
    assert all(p["past"] for p in today["periods"]) and [p["state"] for p in today["periods"]][-1] == "cancelled"
    assert not days[1]["deviates"]
    # „Spät ins Archiv gekommen“ ist keine Zusatzstunde und kein Hinweis wert.
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("UPDATE lessons SET is_late_addition=1 WHERE date='2026-09-28'")
    assert fb.schedule(1, friday, datetime(2026, 9, 25, 14, 0))[1]["notes"] == []
    # Vormittags läuft die zweite Stunde.
    running = fb.schedule(1, friday, datetime(2026, 9, 25, 10, 0))[0]
    assert [p["now"] for p in running["periods"]] == [False, True, False, False]
    # Samstag: Montag und Dienstag; der Dienstag fällt ganz aus und bleibt sichtbar.
    weekend = fb.schedule(1, date(2026, 9, 26), datetime(2026, 9, 26, 9, 0))
    assert [d["date"] for d in weekend] == ["2026-09-28", "2026-09-29"]
    assert weekend[1]["all_cancelled"] and weekend[1]["headline"] == "fällt ganz aus"


def test_an_exam_on_the_calendar_marks_its_lesson(env):
    lessons([(21, "2026-09-28", 750, 835, None)])
    day = fb.schedule(1, date(2026, 9, 28), datetime(2026, 9, 28, 7, 0),
                      [{"date": "2026-09-28", "subject_name": "MATHEMATIK"}])[0]
    assert day["periods"][0]["exam"] and "Mathematik: Arbeit" in day["notes"]


def test_on_the_weekend_the_rings_show_the_friday_state(env, monkeypatch):
    """Am freien Tag zeigen die Ringe den Stand des letzten Schultags (D205):
    Feedback zu den Stunden vom Freitag, Aufgaben wie am Freitagabend."""
    lessons([(31, "2026-09-25", 800, 845, None), (32, "2026-09-25", 850, 935, None),   # Doppelstunde
             (33, "2026-09-25", 1130, 1215, None), (34, "2026-09-28", 800, 845, None)])
    with closing(db.webapp_conn()) as c, c:
        for lid in (31, 32):  # „Heute“ bewertet eine Doppelstunde für beide Stunden
            c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,1,3,'now','now')", (lid,))
        c.execute("INSERT INTO tasks(account_id,title,task_type,status,source,due_date,created_at,updated_at) "
                  "VALUES(1,'Brüche','homework','open','manual','2026-09-28','now','now')")
        c.execute("INSERT INTO tasks(account_id,title,task_type,status,source,due_date,created_at,updated_at,completed_at) "
                  "VALUES(1,'Lesen','homework','done','manual','2026-09-25','now',?,?)",
                  (datetime.now().astimezone().isoformat(), datetime.now().astimezone().isoformat()))
    saturday = fb.rings(1, date(2026, 9, 26), datetime(2026, 9, 26, 10, 0))
    assert saturday["carry_day"] == "2026-09-25" and saturday["next_school_day"] == "2026-09-28"
    # Die Doppelstunde ist bewertet (eine Zeile), die Stunde um 11:30 nicht.
    assert saturday["feedback"] == {"done": 1, "total": 2, "backlog": 0}
    assert saturday["tasks"] == {"done": 1, "total": 2}
    # Am Schultag selbst zählen nur die schon beendeten Stunden.
    friday = fb.rings(1, date(2026, 9, 25), datetime(2026, 9, 25, 10, 0))
    assert friday["carry_day"] is None and friday["feedback"] == {"done": 1, "total": 1, "backlog": 0}


def test_forgotten_feedback_stays_open_until_it_is_caught_up(env):
    """D210: Wie eine überfällige Hausaufgabe bleibt eine vergessene Rückmeldung
    stehen, bis sie nachgeholt ist; erst dann schließt der Ring. Eingefordert
    wird ab Beginn des Schuljahrs; Eltern können einen Tag erlassen."""
    from backend import rewards
    lessons([(50, "2026-07-10", 800, 845, None),                                   # voriges Schuljahr
             (51, "2026-09-23", 800, 845, None), (52, "2026-09-24", 800, 845, None),
             (53, "2026-09-24", 850, 935, None), (54, "2026-09-25", 800, 845, None),
             (55, "2026-09-24", 1000, 1045, "cancelled")])
    now = datetime(2026, 9, 25, 14, 0)
    # Juli liegt vor dem Schuljahr, der ausgefallene Donnerstag zählt nie.
    assert [l["id"] for l in rewards.feedback_backlog(1, date(2026, 9, 25), now)] == [51, 52, 53, 54]
    friday = fb.rings(1, date(2026, 9, 25), now)
    assert friday["feedback"] == {"done": 0, "total": 3, "backlog": 2}  # Mi, Do (Doppelstunde), Fr
    assert rewards.day_state(1, date(2026, 9, 25), now)["feedback_open"] == 4
    # Eltern erlassen den Mittwoch, das Kind war nicht da.
    assert rewards.waive_feedback_day(1, date(2026, 9, 23), 1, now) == 1
    assert [l["id"] for l in rewards.feedback_backlog(1, date(2026, 9, 25), now)] == [52, 53, 54]
    with closing(db.webapp_conn()) as c, c:
        for lid in (52, 53, 54):
            c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,1,2,'now','now')", (lid,))
    assert rewards.feedback_backlog(1, date(2026, 9, 25), now) == []
    assert fb.rings(1, date(2026, 9, 25), now)["feedback"] == {"done": 1, "total": 1, "backlog": 0}


def test_only_parents_waive_a_day_and_only_in_the_past(env, monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from backend import rewards, parent_todo
    from backend.routers import checkins
    lessons([(61, "2026-09-23", 800, 845, None)])
    monkeypatch.setattr(rewards, "now_local", lambda: datetime(2026, 9, 25, 14, 0, tzinfo=rewards.TZ))
    items = parent_todo.feedback_items(1, date(2026, 9, 25))
    assert [i["title"] for i in items] == ["1 Stunde ohne Rückmeldung"]
    assert items[0]["action"]["page"] == "today" and items[0]["action"]["section"] == "nachholen"
    monkeypatch.setattr("backend.routers.learning.access", lambda user, account, write=False, parent=False: (_ for _ in ()).throw(HTTPException(403)) if user.role == "child" else None)
    kid = SimpleNamespace(id=2, role="child", is_admin=False)
    parent = SimpleNamespace(id=1, role="parent", is_admin=False)
    try:
        checkins.waive_feedback(1, checkins.WaiveIn(day=date(2026, 9, 23)), kid)
        assert False, "Kinder erlassen nichts"
    except HTTPException as e:
        assert e.status_code == 403
    try:
        checkins.waive_feedback(1, checkins.WaiveIn(day=date(2026, 9, 25)), parent)
        assert False, "nur vergangene Tage"
    except HTTPException as e:
        assert e.status_code == 400
    assert checkins.waive_feedback(1, checkins.WaiveIn(day=date(2026, 9, 23)), parent) == {"waived": 1}
    assert parent_todo.feedback_items(1, date(2026, 9, 25)) == []


def test_the_today_page_brings_the_last_school_day_on_a_free_day(env, monkeypatch):
    client, state, patch = env
    from backend.routers import today as today_routes
    from backend import rewards
    lessons([(41, "2026-09-25", 800, 845, None), (42, "2026-09-28", 800, 845, None), (43, "2026-09-24", 800, 845, None)])
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,41,1,2,'now','now')")
        c.execute("INSERT OR REPLACE INTO reward_config(id,start_day) VALUES(1,'2026-09-21')")
    monkeypatch.setattr(rewards, "now_local", lambda: datetime(2026, 9, 26, 10, 0, tzinfo=rewards.TZ))
    monkeypatch.setattr(today_routes, "today_local", lambda: date(2026, 9, 26))
    client.app.include_router(today_routes.router, prefix="/api")
    body = client.get("/api/accounts/1/today").json()
    assert body["lessons"] == [] and body["next"]["date"] == "2026-09-28"
    carry = body["carry_lessons"]
    assert carry["date"] == "2026-09-25" and [l["id"] for l in carry["lessons"]] == [41]
    assert carry["lessons"][0]["checkin"]["rating"] == 2
    # Die vergessene Stunde vom Donnerstag steht zum Nachholen darunter (D210).
    assert [l["id"] for l in body["feedback_backlog"]] == [43]
    # An einem Schultag gibt es keinen Übertrag.
    monkeypatch.setattr(today_routes, "today_local", lambda: date(2026, 9, 25))
    assert client.get("/api/accounts/1/today").json()["carry_lessons"] is None
