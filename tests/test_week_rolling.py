"""Die Woche rollend (D184): fünf Schultage ab heute über das Wochenende,
Abweichungen wie auf der Familienkarte, parallele Stunden, Arbeiten mit
Lernstand, Hausaufgaben je Tag und für Vergangenes ein Rückblick."""
import asyncio
import sqlite3
from contextlib import closing
from datetime import date, datetime

from test_learning import env  # noqa: F401
from test_day_close import LESSON_COLUMNS
from backend import db, week_rolling as wr

TODAY = date(2026, 9, 24)   # Donnerstag
MORNING = datetime(2026, 9, 24, 7, 0)
AFTER = datetime(2026, 9, 24, 15, 0)


def lessons(rows):
    """rows: (id, date, start, end, subject[, code[, extra]])"""
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f"CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})")
        for r in rows:
            lid, day, start, end, subject = r[:5]
            code = r[5] if len(r) > 5 else None
            extra = r[6] if len(r) > 6 else {}
            cols = {"id": lid, "account_id": 1, "date": day, "start_time": start, "end_time": end,
                    "subject_name": subject, "code": code, "was_absent": 0, **extra}
            c.execute(f"INSERT INTO lessons({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))


def week(days, start=750):
    """Je Tag zwei Stunden Mathematik."""
    rows, n = [], 100
    for d in days:
        rows += [(n, d, start, start + 45, "Mathematik"), (n + 1, d, start + 55, start + 140, "Deutsch")]
        n += 2
    lessons(rows)


def run(**kw):
    kw.setdefault("today", TODAY)
    kw.setdefault("now", MORNING)
    return asyncio.run(wr.rolling(1, kw.pop("today"), kw.pop("now"), **kw))


def no_exams(patch, found=()):
    from backend import exams

    async def fake(account_id, **kw):
        return {"exams": list(found)}
    patch.setattr(exams, "resolve_exams", fake)


SCHOOL = ["2026-09-24", "2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"]


def test_five_school_days_roll_over_the_weekend(env):
    _, _, patch = env
    no_exams(patch)
    week(SCHOOL)
    data = run()
    assert [d["date"] for d in data["days"]] == SCHOOL[:5]
    assert data["mode"] == "ahead" and data["days"][0]["is_today"] and data["days"][0]["label"] == "Do 24.09."
    assert data["next_from"] == "2026-10-01" and data["prev_before"] is None
    # Nach Schulschluss zählen die fünf Tage ab morgen, heute bleibt oben.
    after = run(now=AFTER)
    assert [d["date"] for d in after["days"]] == SCHOOL[:6]
    # Samstag: ab Montag.
    assert run(today=date(2026, 9, 26), now=datetime(2026, 9, 26, 9, 0))["days"][0]["date"] == "2026-09-28"
    # Hinter dem bekannten Stundenplan Montag bis Freitag als Annahme.
    later = run(start=date(2026, 10, 1))
    assert [d["date"] for d in later["days"]] == ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"]
    assert [d["assumed"] for d in later["days"]] == [False, False, True, True, True]
    assert later["days"][0]["week"] == 40


def test_holidays_are_skipped_and_named(env):
    _, _, patch = env
    no_exams(patch)
    week(SCHOOL)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("CREATE TABLE master_holidays(account_id INTEGER, id INTEGER, name TEXT, longName TEXT, "
                  "startDate TEXT, endDate TEXT)")
        c.execute("INSERT INTO master_holidays VALUES(1,1,'HF','Herbstferien','2026-10-05','2026-10-16')")
    data = run(start=date(2026, 10, 1))
    assert [d["date"] for d in data["days"]] == ["2026-10-01", "2026-10-02", "2026-10-19", "2026-10-20", "2026-10-21"]
    assert [(f["name"], f["label"]) for f in data["free"]] == [("Herbstferien", "Mo 05.10. – Fr 16.10.")]
    # Ein einzelner freier Werktag im bekannten Stundenplan steht als frei da.
    lessons([(900, "2026-09-21", 750, 835, "Mathematik")])
    past = run(before=date(2026, 9, 25))
    assert [d["date"] for d in past["days"]] == ["2026-09-21", "2026-09-24"]
    assert [(f["start"], f["end"], f["label"]) for f in past["free"]] == [("2026-09-22", "2026-09-23", "Di 22.09. – Mi 23.09.")]


def test_early_end_late_start_and_parallel_lessons(env):
    _, _, patch = env
    no_exams(patch)
    lessons([
        (1, "2026-09-24", 750, 835, "Mathematik"), (2, "2026-09-24", 840, 925, "Deutsch"),
        (3, "2026-09-24", 1135, 1220, "Englisch", "cancelled"), (4, "2026-09-24", 1225, 1310, "Englisch", "cancelled"),
        (5, "2026-09-25", 750, 835, "Sport", "cancelled"), (6, "2026-09-25", 840, 925, "Musik"),
        (7, "2026-09-25", 945, 1030, "Spanisch"), (8, "2026-09-25", 945, 1030, "Latein"),
        (9, "2026-09-28", 750, 835, "Physik", None, {"is_room_substituted": 1, "room": "B12"}),
        (10, "2026-09-28", 840, 925, "Chemie", "irregular"),
    ])
    days = {d["date"]: d for d in run()["days"]}
    thu = days["2026-09-24"]["strip"]
    assert thu["headline"] == "früher Schluss 09:25 statt 13:10"
    assert [c["text"] for c in thu["changes"]] == ["Englisch 11:35–13:10 fällt aus"]
    fri = days["2026-09-25"]
    assert fri["strip"]["headline"] == "später Beginn 08:40"
    # Zwei Stunden zur selben Zeit überschreiben sich nicht.
    assert sorted(l["subject_name"] for l in fri["lessons"] if l["start_time"] == 945) == ["Latein", "Spanisch"]
    assert len([p for p in fri["strip"]["periods"] if p["start"] == "09:45"]) == 2
    mon = days["2026-09-28"]["strip"]
    assert [c["kind"] for c in mon["changes"]] == ["sub", "room"]


def test_exams_carry_readiness_and_homework_is_counted_per_day(env):
    _, _, patch = env
    week(SCHOOL)
    no_exams(patch, [{"exam_key": "cal:m", "date": "2026-09-29", "title": "Mathearbeit", "subject_name": "Mathematik"},
                     {"exam_key": "cal:d", "date": "2026-09-30", "title": "Deutsch Test", "subject_name": "Deutsch"}])
    from backend import practice
    patch.setattr(practice, "raster", lambda a, key: {"ready": 1, "total": 2} if key == "cal:m" else {"ready": 0, "total": 0})
    lessons([(50, "2026-09-25", 1000, 1045, "Englisch", None, {"period_info_json": '{"exam": {"name": "Vokabeltest"}}'})])
    with closing(db.webapp_conn()) as c, c:
        for title, due, status in [("A", "2026-09-28", "open"), ("B", "2026-09-28", "open"), ("C", "2026-09-29", "done"),
                                   ("D", "2026-09-30", "open"), ("E", "2026-10-09", "open")]:
            c.execute("INSERT INTO tasks(account_id,title,subject_name,task_type,status,due_date,source,created_at,updated_at)"
                      " VALUES(1,?,'Mathematik','homework',?,?,'manual','x','x')", (title, status, due))
    days = {d["date"]: d for d in run()["days"]}
    assert days["2026-09-29"]["exams"] == [{"exam_key": "cal:m", "subject": "Mathematik", "kind": "Arbeit", "ready": 1, "total": 2}]
    assert days["2026-09-30"]["exams"][0]["kind"] == "Test"
    # Eine Arbeit, die nur UNTIS kennt, ohne Schlüssel; ihre Stunde ist markiert.
    fri = days["2026-09-25"]
    assert fri["exams"] == [{"exam_key": None, "subject": "Englisch", "kind": "Vokabeltest", "ready": 0, "total": 0}]
    assert [p["exam"] for p in fri["strip"]["periods"] if p["subject"] == "Englisch"] == [True]
    assert [p["exam"] for p in days["2026-09-29"]["strip"]["periods"]] == [True, False]
    assert {d: days[d]["tasks_open"] for d in days} == {"2026-09-24": 0, "2026-09-25": 0, "2026-09-28": 2,
                                                         "2026-09-29": 0, "2026-09-30": 1}
    assert [t["title"] for t in days["2026-09-29"]["tasks"]] == ["C"] and days["2026-09-29"]["tasks"][0]["done"]


def test_past_days_bring_a_review_and_open_feedback(env):
    _, _, patch = env
    no_exams(patch)
    week(["2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23"] + SCHOOL)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,100,2,3,'x','x')")
        c.execute("INSERT INTO tasks(account_id,title,task_type,status,due_date,source,created_at,updated_at,completed_at)"
                  " VALUES(1,'X','homework','done','2026-09-18','manual','x','x','2026-09-17T15:00:00+00:00')")
    data = run(before=date(2026, 9, 24))
    assert data["mode"] == "past" and [d["date"] for d in data["days"]][0] == "2026-09-17"
    assert data["review"]["lessons"] == {"held": 10, "rated": 1}
    assert "1 Hausaufgabe erledigt" in data["review"]["lines"] and "1 von 10 Stunden zurückgemeldet" in data["review"]["lines"]
    assert not any("€" in line or "KI" in line for line in data["review"]["lines"])
    assert data["feedback"]["count"] == 9
    # In der Standardansicht stehen die offenen Rückmeldungen wie auf „Heute“
    # (rewards.feedback_backlog): eingefordert ab rewards.FEEDBACK_FROM (21.09.).
    ahead = run()
    assert ahead["review"] is None and ahead["feedback"]["count"] == 6
    assert ahead["feedback"]["days"][0]["date"] == "2026-09-21"


def test_the_week_counts_open_feedback_like_today(env):
    """„Noch zurückmelden“ nach derselben Regel wie Ring und Serie (D210):
    auch älter als sieben Tage, nie ein Eintrag ohne Fach, nie eine erlassene
    Stunde; Teamunterricht (zwei Einträge im selben Fach zur selben Zeit) ist
    eine Stunde. Das gilt auch zurückgeblättert."""
    _, _, patch = env
    no_exams(patch)
    team = {"subject_untis_id": 7}
    lessons([(204, "2026-09-21", 800, 845, "Physik"),
             (201, "2026-09-22", 1035, 1120, "Musik", None, {**team, "teacher_name": "A", "untis_period_id": 1}),
             (202, "2026-09-22", 1035, 1120, "Musik", None, {**team, "teacher_name": "B", "untis_period_id": 2}),
             (203, "2026-09-22", 750, 2359, None),                                          # Klassenfahrt
             (206, "2026-09-22", 800, 845, "Religion"), (207, "2026-09-22", 800, 845, "Werte und Normen")])
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO feedback_waivers(account_id,lesson_id,waived_by,created_at) VALUES(1,204,1,'x')")
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,206,2,3,'x','x')")
    later = dict(today=date(2026, 10, 6), now=datetime(2026, 10, 6, 7, 0))
    ahead = run(**later)
    assert [d["date"] for d in ahead["feedback"]["days"]] == ["2026-09-22"]
    # Werte und Normen läuft parallel zu Religion, ist aber ein anderes Fach: offen.
    assert [l["id"] for l in ahead["feedback"]["days"][0]["lessons"]] == [207, 201, 202]
    assert ahead["feedback"]["count"] == 2
    past = run(before=date(2026, 9, 24), **later)
    assert past["mode"] == "past"
    assert [(d["date"], [l["id"] for l in d["lessons"]]) for d in past["feedback"]["days"]] == [("2026-09-22", [207, 201, 202])]
    assert past["feedback"]["count"] == 2
    # Eine Bewertung für einen der beiden Musik-Einträge schließt die Stunde.
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,202,2,2,'x','x')")
    assert [l["id"] for d in run(**later)["feedback"]["days"] for l in d["lessons"]] == [207]
    assert [l["id"] for d in run(before=date(2026, 9, 24), **later)["feedback"]["days"] for l in d["lessons"]] == [207]


def test_the_endpoint_answers_in_one_call(env):
    client, _, patch = env
    no_exams(patch)
    from backend.routers import week as week_routes
    client.app.include_router(week_routes.router, prefix="/api")
    week(SCHOOL)
    from backend import learning
    patch.setattr(learning, "today_local", lambda: TODAY)
    r = client.get("/api/accounts/1/week/rolling")
    assert r.status_code == 200 and r.json()["days"][0]["date"] == "2026-09-24"
    r = client.get("/api/accounts/1/week/rolling?from=2026-09-28&days=3")
    assert [d["date"] for d in r.json()["days"]] == ["2026-09-28", "2026-09-29", "2026-09-30"]
    assert client.get("/api/accounts/1/week/rolling?from=gestern").status_code == 400


def test_holiday_names_read_as_latin1_are_repaired():
    assert wr.repair_text("Osterferien BrÃ¼ckentag") == "Osterferien Brückentag"
    assert wr.repair_text("Herbstferien") == "Herbstferien"
    assert wr.repair_text("Ã€ßx€") == "Ã€ßx€", "geht die Rückwandlung nicht auf, bleibt der Text"
