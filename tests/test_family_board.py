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


def quiet(patch, bag=None, feedback=None, retakes=()):
    patch.setattr(fb, "next_school_day", lambda a, t: "2026-09-25" if bag else None)
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
    assert by["retake"]["go"]["page"] == "materialien" and by["retake"]["go"]["section"] == "fotos"
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
