"""Serie, Retten und Abzeichen (D172, D173)."""
from contextlib import closing
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from test_learning import env, child  # noqa: F401
from backend import db, packing, rewards, view_mode

TZ = ZoneInfo("Europe/Berlin")
KID = SimpleNamespace(id=2, role="child")
PARENT = SimpleNamespace(id=1, role="parent")
START = date(2026, 9, 28)  # Montag


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)


@pytest.fixture
def world(env, monkeypatch):
    plan = {}  # Tag -> Liste von Stunden

    def lessons(account, first, last):
        out, d = [], first
        while d <= last:
            out += [dict(l, date=d.isoformat()) for l in plan.get(d, [])]
            d += timedelta(days=1)
        return out
    monkeypatch.setattr(rewards, "_lessons", lessons)
    monkeypatch.setattr(packing, "packing_plan", lambda account, day: ([{"key": "subject:ma"}] if plan.get(day) else [], "x", []))
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_config(id,start_day) VALUES(1,?)", (START.isoformat(),))
    return plan


def school(plan, day, lid, absent=False):
    plan[day] = [{"id": lid, "start_time": 750, "end_time": 1310, "was_absent": absent}]


def finish(day, lid, due):
    """Alles erledigen, was für den Tag gilt: Rückmeldung, Tasche für den nächsten Schultag."""
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT OR REPLACE INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,2,3,'t','t')", (lid,))
        c.execute("INSERT OR REPLACE INTO packing_items VALUES(1,?,'subject:ma',1,1,'t',2)", (due.isoformat(),))


def kinds():
    with closing(db.webapp_conn()) as c:
        return {r["school_day"]: r["kind"] for r in c.execute("SELECT * FROM reward_days")}


def test_a_day_counts_only_when_clear_and_the_child_acted(world):
    mon, tue = START, START + timedelta(days=1)
    school(world, mon, 1); school(world, tue, 2)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO tasks(id,account_id,title,task_type,status,due_date,source,created_at,updated_at) VALUES(9,1,'Mathe','homework','open',?,'manual','t','t')", (tue.isoformat(),))
    finish(mon, 1, tue)
    rewards.note(1, "feedback", 1, PARENT, at(mon, 15))
    rewards.evaluate(1, at(mon, 15))
    assert kinds() == {}, "Eltern zählen nicht, und die Aufgabe ist noch offen"
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE tasks SET status='done'")
    rewards.note(1, "task", 9, KID, at(mon, 15, 30))
    assert kinds() == {mon.isoformat(): "full"}
    s = rewards.summary(1, at(mon, 16))
    assert s["streak"]["current"] == 1 and s["today"]["bonus"] is True
    assert next(b for b in s["badges"] if b["key"] == "fruehstarter")["value"] == 1


def test_rescue_until_first_lesson_once_per_week(world):
    mon, tue, wed, thu = (START + timedelta(days=i) for i in range(4))
    for i, d in enumerate((mon, tue, wed, thu), 1):
        school(world, d, i)
    rewards.note(1, "feedback", 1, KID, at(mon, 14))  # Montag angefangen, nicht fertig
    finish(mon, 1, tue)
    rewards.evaluate(1, at(tue, 7, 30))  # vor der ersten Stunde am Dienstag nachgeholt
    assert kinds()[mon.isoformat()] == "rescued"
    rewards.note(1, "feedback", 2, KID, at(tue, 14))
    finish(tue, 2, wed)
    rewards.evaluate(1, at(wed, 7, 30))
    assert tue.isoformat() not in kinds(), "nur einmal je Woche"
    s = rewards.summary(1, at(wed, 8))
    assert s["streak"]["current"] == 0 and s["streak"]["record"] == 1
    rewards.evaluate(1, at(thu, 8))  # zu spät für Mittwoch
    assert wed.isoformat() not in kinds()


def test_weekend_and_sick_days_pause_the_streak(world):
    fri, mon, tue = START + timedelta(days=4), START + timedelta(days=7), START + timedelta(days=8)
    school(world, fri, 1); school(world, mon, 2, absent=True); school(world, tue, 3)
    school(world, tue + timedelta(days=1), 4)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_days VALUES(1,?,'full','t',0)", (fri.isoformat(),))
        c.execute("INSERT INTO reward_days VALUES(1,?,'full','t',0)", (tue.isoformat(),))
    s = rewards.summary(1, at(tue, 18))
    assert s["streak"]["current"] == 2
    assert s["total"] == 2


def test_child_mode_counts_test_mode_never(world):
    token = view_mode.current.set("child")
    try:
        assert rewards.acting_child(PARENT)
    finally:
        view_mode.current.reset(token)
    token = view_mode.current.set("test")
    try:
        assert not rewards.acting_child(KID)
    finally:
        view_mode.current.reset(token)
    assert not rewards.acting_child(PARENT)


def test_first_school_year_medals_are_easier(world):
    assert rewards.MEDAL_LIMITS["2026/27"] == (0.50, 0.65, 0.80)
    assert rewards.school_year(date(2026, 9, 28)) == "2026/27"
    assert rewards.school_year(date(2027, 7, 30)) == "2026/27"
    assert rewards.school_year(date(2027, 8, 1)) == "2027/28"


def test_friday_counts_fully_until_sunday_evening_then_only_rescued(world):
    fri = START + timedelta(days=4)
    sat, sun, mon = fri + timedelta(days=1), fri + timedelta(days=2), fri + timedelta(days=3)
    school(world, fri, 1); school(world, mon, 2)
    rewards.note(1, "feedback", 1, KID, at(fri, 14))   # Freitag angefangen, Tasche fehlt
    rewards.evaluate(1, at(fri, 18))
    assert kinds() == {}
    finish(fri, 1, mon)
    rewards.note(1, "bag", "mon", KID, at(sun, 19))   # am Sonntag fertig gemacht
    assert kinds() == {fri.isoformat(): "full"}, "bis Sonntag erledigt zählt voll"
    s = rewards.summary(1, at(sun, 20))
    assert s["streak"]["current"] == 1


def test_after_the_weekend_friday_is_only_rescued(world):
    fri = START + timedelta(days=4)
    sat, mon = fri + timedelta(days=1), fri + timedelta(days=3)
    school(world, fri, 1); school(world, mon, 2)
    rewards.note(1, "feedback", 1, KID, at(fri, 14))
    rewards.evaluate(1, at(sat, 10))
    assert kinds() == {}
    finish(fri, 1, mon)
    rewards.evaluate(1, at(mon, 7, 20))
    assert kinds() == {fri.isoformat(): "rescued"}
