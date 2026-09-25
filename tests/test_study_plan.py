"""Lern-Pflichtplan des Tages (D180, D188): Bedarf je Arbeit aus dem Raster, ohne
Deckel verteilt bis zum Puffer vor der Arbeit, Wochenende nur wenn nötig,
Einfrieren, Erledigt, Grundpensum und „Geschafft“ mit Lernen."""
import sys
import types
from contextlib import closing
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from test_learning import env, child  # noqa: F401
from backend import db, mentor_opening, packing, rewards, study_plan as sp

TZ = ZoneInfo("Europe/Berlin")
KID = SimpleNamespace(id=2, role="child")
PARENT = SimpleNamespace(id=1, role="parent", is_admin=False)
MON = date(2026, 9, 28)  # Montag
SAT = MON + timedelta(days=5)


def at(day, hh, mm=0):
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)


@pytest.fixture
def world(env, monkeypatch):
    """Schule montags bis freitags, sonst nichts. Kein Vokabelpensum."""
    plan = {"free": set()}

    def lessons(account, first, last):
        out, d, lid = [], first, 0
        while d <= last:
            if d.weekday() < 5 and d not in plan["free"]:
                lid = int(d.strftime("%Y%m%d"))
                out.append({"id": lid, "date": d.isoformat(), "start_time": 800, "end_time": 1300,
                            "subject_name": "Deutsch", "lstext": "Kommasetzung"})
            d += timedelta(days=1)
        return out
    monkeypatch.setattr(rewards, "_lessons", lessons)
    monkeypatch.setattr(packing, "packing_plan", lambda account, day: ([], "x", []))
    monkeypatch.setitem(sys.modules, "backend.vocab_pensum", types.SimpleNamespace(daily=lambda a, d: []))
    return plan


def vocab(monkeypatch, items):
    mod = types.SimpleNamespace(daily=lambda a, d: [dict(i) for i in items])
    monkeypatch.setitem(sys.modules, "backend.vocab_pensum", mod)
    import backend
    monkeypatch.setattr(backend, "vocab_pensum", mod, raising=False)


def exam(key, subject, day, titles):
    mentor_opening.remember_exam(1, key, day.isoformat())
    ids = []
    with closing(db.webapp_conn()) as c, c:
        for i, t in enumerate(titles):
            ids.append(c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,position,title,created_at,updated_at) "
                                 "VALUES(1,?,?,?,?,'t','t')", (subject, key, i, t)).lastrowid)
    return ids


def answer(topic, afb=1, points=4, when=None, source=None, fmt=None, attempt=None):
    when = when or at(MON, 10)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO topic_answers(account_id,topic_id,session_id,result,afb,created_at,points,max_points,source,paper_format,attempt_id) "
                  "VALUES(1,?,1,?,?,?,?,4,?,?,?)",
                  (topic, "correct" if points >= 3.2 else "partial", afb, when.isoformat(), points, source, fmt, attempt))


def ready(topic, when=None, source="paper", fmt=None):
    """I und II sicher: je die letzten vier Aufgaben voll."""
    for afb in (1, 2):
        for _ in range(4):
            answer(topic, afb, 4, when, source, fmt)


def keys(steps):
    return [(s["kind"], s.get("format"), s.get("exam_key")) for s in steps]


def seq(key="ma"):
    return [(x["kind"], x["format"]) for p in sp.plans(1, MON) if p["exam_key"] == key for x in p["sequence"]]


def test_sequence_per_exam_from_the_raster(world):
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme", "Gleichungen", "Vokabeln Unit 1"])
    assert seq() == [("paper", "einstieg"), ("dialog", None), ("paper", "kurz"), ("dialog", None), ("paper", "kurz"),
                     ("paper", "probe")], "alles offen; Vokabelthema zählt nicht"
    answer(ids[0], 1, 1, source="paper")  # Einstieg gemacht, Terme wackeln
    ready(ids[1])
    assert seq() == [("dialog", None), ("paper", "kurz"), ("paper", "probe")]
    answer(ids[0], 1, 2, source=None)  # zuletzt im Gespräch geübt → gleich der Nachweis
    assert seq() == [("paper", "kurz"), ("paper", "probe")]
    ready(ids[0])
    assert seq() == [("paper", "probe")], "alles sicher: Probearbeit"
    answer(ids[0], 1, 4, when=at(MON - timedelta(days=1), 10), fmt="probe")
    assert seq() == [] and sp.compute(1, MON) == [], "Probearbeit vor kurzem: keine zweite"


def test_behind_in_the_buffer_everything_today(world):
    exam("en", "Englisch", MON + timedelta(days=1), ["Tenses"])
    steps = sp.compute(1, MON)
    assert [s["format"] for s in steps] == ["einstieg", None, "kurz", "probe"] and all(s["tight"] for s in steps)


def test_no_cap_nearest_exam_first(world):
    far = exam("ge", "Geschichte", MON + timedelta(days=20), ["A", "B"])
    near = exam("bi", "Biologie", MON + timedelta(days=4), ["A", "B"])
    mid = exam("ph", "Physik", MON + timedelta(days=8), ["A", "B"])
    ready(far[0]); ready(mid[0])
    steps = sp.compute(1, MON)
    got = [s["exam_key"] for s in steps]
    # Biologie: 6 Schritte in 2 Lerntagen vor dem Puffer → heute 3; Physik: 3 in 4 → heute 1.
    assert got[:4] == ["bi", "bi", "bi", "ph"], got
    plans = {p["exam_key"]: p for p in sp.plans(1, MON)}
    assert plans["bi"]["need"] == 6 and plans["bi"]["days"] == 2 and plans["ge"]["need"] == 3
    assert "Biologie am 02.10.: noch etwa 6 Schritte in 2 Lerntagen" in sp.outlook(1, MON)


def test_weekend_free_unless_the_school_days_do_not_suffice(world, monkeypatch):
    exam("ma", "Mathematik", SAT + timedelta(days=9), ["A", "B"])
    assert sp.compute(1, SAT) == [], "Wochenende frei: 6 Schritte in 3 Schultagen reichen"
    exam("fr", "Französisch", SAT + timedelta(days=3), ["A", "B", "C"])  # Dienstag: 8 Schritte, ein Schultag
    steps = sp.compute(1, SAT)
    assert [s["exam_key"] for s in steps] == ["fr"] * 3 and steps[0]["format"] == "einstieg" and steps[0]["tight"]
    view = sp.view(1, SAT, store=False)
    assert view["engpass"] and view["free_day"] and view["tight"] == [{"subject": "Französisch", "exam_date": "2026-10-06"}]
    assert view["outlook"].startswith("Es wird eng. Französisch am 06.10.")
    # Ferien wie Wochenende.
    world["free"].update(MON + timedelta(days=i) for i in range(5))
    assert {s["exam_key"] for s in sp.compute(1, MON)} == {"fr"}, "in den Ferien nur, was sonst nicht reicht"
    world["free"].clear()
    # Vokabeltest steht an: zusätzlich Pflicht.
    vocab(monkeypatch, [{"subject": "Englisch", "unit": "Unit 2", "target": 20, "done": False, "href": "#/vokabeln",
                         "exam_key": "voc", "why": "Test am Freitag."}])
    assert sp.compute(1, MON)[-1]["kind"] == "vocab"
    assert sp.compute(1, SAT)[-1]["kind"] == "vocab", "am Wochenende entscheidet das Pensum selbst"


def test_basic_daily_step_fallbacks(world, monkeypatch):
    assert sp.compute(1, MON) == [], "nichts offen, keine Rückmeldung: kein Schritt"
    lid = int((MON - timedelta(days=3)).strftime("%Y%m%d"))
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,2,1,'t','t')", (lid,))
    s = sp.compute(1, MON)[0]
    assert s["kind"] == "dialog" and s["lesson_id"] == lid and s["href"].startswith("#/learning?lesson_id=")
    assert sp.compute(1, SAT) == [], "Grundpensum nur an Schultagen"
    vocab(monkeypatch, [{"subject": "Englisch", "unit": "Unit 2", "target": 20, "done": False, "href": "#/vokabeln", "exam_key": None, "why": "x"},
                        {"subject": "Latein", "unit": "L3", "target": 10, "done": False, "href": "#/vokabeln", "exam_key": None, "why": "y"}])
    assert keys(sp.compute(1, MON)) == [("vocab", None, None)], "Vokabeln vor der Rückmeldung, ein Schritt reicht"


def test_plan_freezes_per_day_and_parent_only_reads(world):
    ids = exam("ma", "Mathematik", MON + timedelta(days=4), ["Terme"])
    assert sp.view(1, MON, store=False)["frozen"] is False
    assert sp.stored(1, MON) is None, "Eltern halten nichts fest"
    first = sp.ensure(1, MON)
    assert keys(first) == [("paper", "einstieg", "ma"), ("dialog", None, "ma")]
    ready(ids[0])
    assert keys(sp.ensure(1, MON)) == keys(first), "innerhalb des Tages bleibt der Plan"
    assert keys(sp.ensure(1, MON + timedelta(days=1))) == [("paper", "probe", "ma")], "am nächsten Tag neu gerechnet"


def test_done_detection(world):
    ids = exam("ma", "Mathematik", MON + timedelta(days=4), ["Terme", "Gleichungen"])
    answer(ids[0], 1, 1, source="paper", when=at(MON - timedelta(days=2), 10))
    ready(ids[1], when=at(MON - timedelta(days=2), 10))
    step = sp.ensure(1, MON)[0]
    assert step["kind"] == "dialog" and step["topic_id"] == ids[0]
    answer(ids[0], 1, 2, when=at(MON, 15)); answer(ids[0], 1, 2, when=at(MON, 15, 5))
    assert not sp.mark_done(1, [step], MON)[0]["done"]
    answer(ids[1], 1, 4, when=at(MON, 15, 6))  # anderes Thema: freiwillig, zählt nicht
    assert not sp.mark_done(1, [step], MON)[0]["done"]
    answer(ids[0], 1, 3, when=at(MON, 15, 10))
    assert sp.mark_done(1, [step], MON)[0]["done"] and sp.open_count(1, MON) == 1, "der Kurztest bleibt offen"
    # Papier: eine heute ausgewertete Arbeit dieser Arbeit, gleich welches Format.
    paper = {"kind": "paper", "exam_key": "ma", "format": "kurz", "key": "paper:ma:kurz:"}
    with closing(db.webapp_conn()) as c, c:
        eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,created_at,status,exam_key,paper_format) "
                        "VALUES(1,'Ü','Mathematik','{}','[]',20,'t','published','ma','mix')").lastrowid
        aid = c.execute("INSERT INTO mentor_exam_attempts(account_id,exam_id,user_id,snapshot,started_at,status,is_test,submitted_at) "
                        "VALUES(1,?,2,'{}','t','graded',0,?)", (eid, at(MON, 16).isoformat())).lastrowid
    assert sp.mark_done(1, [paper], MON)[0]["done"]
    two = sp.mark_done(1, [paper, {**paper, "key": "paper:ma:probe:", "format": "probe"}], MON)
    assert [x["done"] for x in two] == [True, False], "je Papier-Schritt eine ausgewertete Arbeit"
    assert not sp.mark_done(1, [paper], MON + timedelta(days=1))[0]["done"], "gestern ist nicht heute"
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_exam_attempts SET is_test=1 WHERE id=?", (aid,))
    assert not sp.mark_done(1, [paper], MON)[0]["done"], "Elternarbeit zählt nicht"


def test_geschafft_needs_learning(world, monkeypatch):
    tue = MON + timedelta(days=1)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_config(id,start_day) VALUES(1,?)", (MON.isoformat(),))
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,2,3,'t','t')",
                  (int(MON.strftime("%Y%m%d")),))
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    answer(ids[0], 1, 1, source="paper", when=at(MON - timedelta(days=2), 10))
    one = {"key": f"dialog:{ids[0]}", "kind": "dialog", "topic_id": ids[0], "subject": "Mathematik", "exam_key": "ma",
           "exam_date": (MON + timedelta(days=9)).isoformat(), "title": "Terme", "why": "x", "format": None, "level": None, "href": "#"}
    monkeypatch.setattr(sp, "compute", lambda a, d: [one])
    rewards.note(1, "feedback", 1, KID, at(MON, 14))
    state = rewards.day_state(1, MON, at(MON, 14))
    assert state["learning_open"] == 1 and not state["clear"]
    with closing(db.webapp_conn()) as c:
        assert not c.execute("SELECT 1 FROM reward_days").fetchone()
    for m in range(3):
        answer(ids[0], 1, 3, when=at(MON, 15, m))
    rewards.note(1, "learn", "dialog:x", KID, at(MON, 15, 5))
    assert rewards.day_state(1, MON, at(MON, 15, 5))["clear"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT kind FROM reward_days WHERE school_day=?", (MON.isoformat(),)).fetchone()[0] == "full"
    # Ohne eingefrorenen Plan zählt Lernen nicht (kein Plan, keine Pflicht).
    assert rewards.day_state(1, tue, at(tue, 14))["learning_open"] == 0


def test_rescue_counts_learning_done_next_morning(world, monkeypatch):
    tue = MON + timedelta(days=1)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_config(id,start_day) VALUES(1,?)", (MON.isoformat(),))
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,2,3,'t','t')",
                  (int(MON.strftime("%Y%m%d")),))
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    answer(ids[0], 1, 1, source="paper", when=at(MON - timedelta(days=2), 10))
    one = {"key": f"dialog:{ids[0]}", "kind": "dialog", "topic_id": ids[0], "subject": "Mathematik", "exam_key": "ma",
           "exam_date": (MON + timedelta(days=9)).isoformat(), "title": "Terme", "why": "x", "format": None, "level": None, "href": "#"}
    later = {**one, "key": "paper:ma:kurz:", "kind": "paper", "format": "kurz"}
    monkeypatch.setattr(sp, "compute", lambda a, d: [one] if d == MON else [later])  # Dienstag noch offen
    rewards.note(1, "feedback", 1, KID, at(MON, 14))
    for m in range(3):
        answer(ids[0], 1, 3, when=at(tue, 7, m))
    rewards.note(1, "learn", "dialog:y", KID, at(tue, 7, 30))
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT kind FROM reward_days WHERE school_day=?", (MON.isoformat(),)).fetchone()[0] == "rescued"


def test_endpoint_and_today_payload(env, world):
    from backend.routers import study_plan as routes, today as today_routes
    client, state, monkeypatch = env
    client.app.include_router(routes.router, prefix="/api")
    monkeypatch.setattr(rewards, "now_local", lambda: at(MON, 15))
    exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    r = client.get("/api/accounts/1/study-plan/today").json()
    assert r["read_only"] and not r["frozen"] and r["steps"][0]["format"] == "einstieg"
    assert set(r["steps"][0]) >= {"key", "kind", "title", "why", "subject", "exam_key", "exam_date", "format",
                                  "topic_id", "level", "href", "done"}
    assert sp.stored(1, MON) is None
    child(state)
    r = client.get("/api/accounts/1/study-plan/today").json()
    assert r["frozen"] and not r["read_only"] and r["total"] == 1 and r["done"] == 0
    assert today_routes._study_plan(1, KID)["steps"][0]["key"] == "paper:ma:einstieg:"


def test_dialog_answer_rechecks_the_day(world, monkeypatch):
    from backend.routers import mentor
    seen = []
    monkeypatch.setattr(rewards, "note", lambda a, kind, ref, user, when=None: seen.append((kind, ref)))
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    mentor.note_learning(1, 1, KID)
    answer(ids[0], 1, 3)
    mentor.note_learning(1, 1, KID)
    assert seen == [("learn", f"dialog:{1}")]
