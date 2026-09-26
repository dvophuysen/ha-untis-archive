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
            if d.weekday() < 5 and d not in plan["free"] and d >= plan.get("since", date.min):
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
    # Biologie: 6 Schritte in 2 Schultagen vor dem Puffer, es wird eng → heute 3
    # und nur Biologie (D215); Physik (3 in 4) wartet.
    assert got == ["bi", "bi", "bi"], got
    plans = {p["exam_key"]: p for p in sp.plans(1, MON)}
    assert plans["bi"]["need"] == 6 and plans["bi"]["days"] == 2 and plans["ge"]["need"] == 3
    assert "Biologie am 02.10.: noch etwa 6 Schritte in 2 Schultagen" in sp.outlook(1, MON)


def test_an_exam_in_the_next_two_school_days_that_is_not_safe_is_all_there_is(world):
    """Notfall (D213): Mathe am Montag, Stand schlecht. Die Freitagsliste hat nur
    Mathe; Einstiegstests für Musik (eine Woche später) und Englisch (ein Monat)
    warten. Am Dienstag ist die Mathearbeit geschrieben, dann kommen die anderen."""
    fri = MON - timedelta(days=3)
    exam("ma", "Mathematik", MON, ["Gleichungen", "Wertetabellen"])
    exam("mu", "Musik", MON + timedelta(days=7), ["Notenwerte"])
    exam("en", "Englisch", MON + timedelta(days=32), ["Tenses"])
    steps = sp.compute(1, fri)
    assert steps and {s["exam_key"] for s in steps} == {"ma"}, [s["key"] for s in steps]
    # Zwei Schultage vorher gilt noch der Wechsel (D189), sofern Zeit ist.
    later = sp.compute(1, MON + timedelta(days=1))
    assert "mu" in {s["exam_key"] for s in later}
    # Hat die nahe Arbeit nichts mehr offen, wartet nichts.
    assert sp._focus(1, fri, [{"exam_key": "ma", "exam_date": MON.isoformat(), "need": 0, "steps": []}]) == set()


def test_an_entry_test_goes_once_the_state_is_measured(world):
    """D215: Misst schon eine andere Arbeit den Stand (etwa eine Probearbeit),
    fällt der Einstiegstest der festgehaltenen Liste als „nicht mehr nötig“ weg."""
    t = exam("ma", "Mathematik", MON + timedelta(days=1), ["Gleichungen"])[0]
    steps = sp.compute(1, MON)
    assert steps[0]["format"] == "einstieg"
    answer(t, 2, 2)
    first = sp.mark_done(1, steps, MON)[0]
    assert first["done"] and first["skipped"] and "schon gemessen" in first["why"]


def test_a_fixed_list_is_shown_next_exam_first(world):
    """D215: Auch eine schon festgehaltene Liste steht nach Termin, ohne dass
    etwas dazukommt oder wegfällt."""
    import json
    steps = [{"key": "en", "kind": "dialog", "title": "E", "exam_date": "2026-10-01"},
             {"key": "voc", "kind": "vocab", "title": "V", "exam_date": None},
             {"key": "ma", "kind": "dialog", "title": "M", "exam_date": "2026-09-30"}]
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO study_plan_days(account_id,day,steps_json,computed_at) VALUES(1,?,?,'t')", (MON.isoformat(), json.dumps(steps)))
    assert [s["key"] for s in sp.view(1, MON, store=False)["steps"]] == ["ma", "en", "voc"]


def test_the_one_time_cleanup_keeps_only_maths(env):
    import json
    steps = [{"key": "a", "subject": "Mathematik"}, {"key": "b", "subject": "Musik"},
             {"key": "c", "subject": "Englisch"}, {"key": "d", "subject": "Mathematik"}]
    sql = dict(db._MIGRATIONS)["plan_focus_001_konto1_20260925"]
    with closing(db.webapp_conn()) as c, c:
        for acc in (1, 2):
            c.execute("INSERT INTO study_plan_days(account_id,day,steps_json,computed_at) VALUES(?,?,?,'t')",
                      (acc, "2026-09-25", json.dumps(steps)))
        c.execute("INSERT INTO study_plan_days(account_id,day,steps_json,computed_at) VALUES(1,'2026-09-24',?,'t')", (json.dumps(steps),))
        c.executescript(sql)
        got = {(r[0], r[1]): [s["key"] for s in json.loads(r[2])] for r in c.execute("SELECT account_id,day,steps_json FROM study_plan_days")}
    assert got[(1, "2026-09-25")] == ["a", "d"]
    assert got[(2, "2026-09-25")] == ["a", "b", "c", "d"] and got[(1, "2026-09-24")] == ["a", "b", "c", "d"]


def test_without_a_squeeze_the_next_exam_comes_first_then_the_later_one(world, monkeypatch):
    """Nächste Arbeit zuerst, spätere danach, nicht im Wechsel (D215)."""
    def plan(key, when, n):
        return {"exam_key": key, "exam_date": when, "need": n, "weekend": False, "behind": False,
                "steps": [{"key": f"{key}{i}", "kind": "dialog", "exam_key": key} for i in range(n)]}
    monkeypatch.setattr(sp, "plans", lambda a, d: [plan("ph", "2026-10-20", 2), plan("bi", "2026-10-12", 2)])
    assert [s["key"] for s in sp.compute(1, MON)] == ["bi0", "bi1", "ph0", "ph1"]


def test_no_new_tasks_on_the_weekend_the_friday_list_carries_it(world, monkeypatch):
    fri = MON + timedelta(days=4)
    exam("ma", "Mathematik", SAT + timedelta(days=9), ["A", "B"])
    assert not [s for s in sp.compute(1, fri) if s["exam_key"] == "ma" and s["tight"]], "Schultage reichen: kein Notpuffer"
    exam("fr", "Französisch", SAT + timedelta(days=3), ["A", "B", "C"])  # Dienstag: 8 Schritte, Fr und Mo
    steps = [s for s in sp.compute(1, fri) if s["exam_key"] == "fr"]
    # Freitag trägt seinen Anteil und den des Wochenendes: 8 × 3/4 = 6.
    assert len(steps) == 6 and steps[0]["format"] == "einstieg" and steps[0]["tight"]
    assert sp.compute(1, SAT) == [] and sp.compute(1, SAT + timedelta(days=1)) == [], "am Wochenende nichts Neues"
    view = sp.view(1, fri, store=False)
    assert view["engpass"] and view["tight"][0] == {"subject": "Französisch", "exam_date": "2026-10-06"}
    assert view["outlook"].startswith("Es wird eng. Französisch am 06.10.")
    assert view["outlook"].endswith("Diese Liste gilt bis Sonntagabend, am Wochenende kommt nichts Neues dazu.")
    # Ferien wie Wochenende: keine neuen Aufgaben.
    world["free"].update(MON + timedelta(days=i) for i in range(5))
    assert sp.compute(1, MON) == []
    world["free"].clear()
    # Französisch am Dienstag ist ein Notfall (D213); ein Vokabeltest am Montag
    # gehört ins selbe Fenster und steht als nächste Prüfung vorn (D215).
    vocab(monkeypatch, [{"subject": "Englisch", "unit": "Unit 2", "target": 20, "done": False, "href": "#/vokabeln",
                         "exam_key": "voc", "exam_date": (SAT + timedelta(days=2)).isoformat(), "why": "Test am Montag."}])
    kinds = [s["kind"] for s in sp.compute(1, fri)]
    assert kinds[0] == "vocab" and len(kinds) > 1, "der Vokabeltest am Montag kommt vor der Arbeit am Dienstag"
    vocab(monkeypatch, [{"subject": "Englisch", "unit": "Unit 2", "target": 20, "done": False, "href": "#/vokabeln",
                         "exam_key": "voc", "exam_date": (SAT + timedelta(days=6)).isoformat(), "why": "Test am Freitag."}])
    assert "vocab" not in [s["kind"] for s in sp.compute(1, fri)], "ein späterer Vokabeltest wartet im Notfall"
    assert sp.compute(1, SAT) == []


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
    # Offene Rückmeldungen der Vortage hielten den Tag offen (D210): hier gibt es keine.
    world["since"] = MON
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
    # Offene Rückmeldungen der Vortage hielten den Tag offen (D210): hier gibt es keine.
    world["since"] = MON
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


def test_friday_carries_the_weekend_and_unknown_timetable_is_weekdays(world, monkeypatch):
    """Arbeit am Mittwoch, heute Freitag: Puffer Montag und Dienstag; die
    Freitagsliste trägt alles, das Wochenende ist Notpuffer. Hinter dem bekannten
    Stundenplan zählen Mo–Fr."""
    fri = MON + timedelta(days=4)
    exam("ma", "Mathematik", fri + timedelta(days=5), ["A", "B"])  # Mittwoch
    p = {x["exam_key"]: x for x in sp.plans(1, fri)}["ma"]
    assert p["need"] == 6 and p["days"] == 1 and p["weekend"]
    assert len(p["steps"]) == 6, "Freitag trägt auch den Anteil des Wochenendes"
    # Nur zwei Wochen Stundenplan bekannt: eine Arbeit in fünf Wochen bekommt nicht täglich mehrere Schritte.
    known = MON + timedelta(days=11)
    orig = rewards._lessons
    monkeypatch.setattr(rewards, "_lessons", lambda a, first, last: [l for l in orig(a, first, last) if l["date"] <= known.isoformat()])
    exam("po", "Politik", MON + timedelta(days=35), ["A", "B", "C"])
    far = {x["exam_key"]: x for x in sp.plans(1, MON)}["po"]
    assert far["days"] > 15 and len(far["steps"]) <= 1 and not far["weekend"]


def test_frozen_plan_is_recomputed_only_on_the_introduction_day(world, monkeypatch):
    intro = date(2026, 9, 25)
    old = [{"key": "alt", "kind": "dialog", "title": "alt", "why": "", "subject": "", "exam_key": None,
            "exam_date": None, "format": None, "topic_id": None, "level": None, "href": "#"}]
    with closing(db.webapp_conn()) as c, c:
        for d in (intro, MON):
            c.execute("INSERT INTO study_plan_days(account_id,day,steps_json,computed_at) VALUES(1,?,?,'t')",
                      (d.isoformat(), '[{"key": "alt", "kind": "dialog"}]'))
    monkeypatch.setattr(sp, "compute", lambda a, d: [{**old[0], "key": "neu"}])
    assert [s["key"] for s in sp.ensure(1, intro)] == ["neu"], "am Einführungstag neu gerechnet"
    assert [s["key"] for s in sp.ensure(1, intro)] == ["neu"]
    assert [s["key"] for s in sp.ensure(1, MON)] == ["alt"], "sonst bleibt der Tag, wie er war"


def test_open_paper_is_offered_again_even_when_only_reading(world):
    """D191: Eine heute angelegte Übungsarbeit hängt am Papier-Schritt, damit sie
    sich wieder öffnen lässt, auch beim Mitlesen."""
    exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    with closing(db.webapp_conn()) as c, c:
        eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,created_at,status,exam_key,paper_format) "
                        "VALUES(1,'Ü','Mathematik','{}','[]',30,'t','published','ma','einstieg')").lastrowid
        aid = c.execute("INSERT INTO mentor_exam_attempts(account_id,exam_id,user_id,snapshot,started_at,status,is_test) "
                        "VALUES(1,?,2,'{}',?,'active',0)", (eid, at(MON, 15).isoformat())).lastrowid
    view = sp.view(1, MON, store=False)
    assert view["read_only"] and view["steps"][0]["format"] == "einstieg" and view["steps"][0]["attempt_id"] == aid


def test_each_short_test_belongs_to_its_topic(world):
    """Zwei Kurztests zugleich: Ein laufender oder ausgewerteter Kurztest zum
    zweiten Thema hängt am Schritt dieses Themas, nicht am ersten (Nutzer: „Es
    wäre gut, wenn die Kurztests gleichzeitig unabhängig voneinander begonnen
    werden könnten“)."""
    import json
    first, second = exam("ma", "Mathematik", MON + timedelta(days=1), ["Gleichungen", "Wertetabellen"])
    for t in (first, second):
        answer(t, 2, 4)  # gemessen, damit kein Einstiegstest vorn steht
    steps = [s for s in sp.compute(1, MON) if s.get("format") == "kurz"]
    assert {s["topic_id"] for s in steps} == {first, second}

    def paper(topic, status, when):
        with closing(db.webapp_conn()) as c, c:
            eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,created_at,status,exam_key,paper_format) "
                            "VALUES(1,'K','Mathematik','{}','[]',20,'t','published','ma','kurz')").lastrowid
            return c.execute("INSERT INTO mentor_exam_attempts(account_id,exam_id,user_id,snapshot,started_at,status,is_test,submitted_at) "
                             "VALUES(1,?,2,?,?,?,0,?)", (eid, json.dumps({"tasks": [{"topic_id": topic, "points": 4}]}),
                                                         when.isoformat(), status, when.isoformat())).lastrowid
    running = paper(second, "grading", at(MON, 15))
    view = {s["topic_id"]: s for s in sp.view(1, MON, store=False)["steps"] if s.get("format") == "kurz"}
    assert view[second]["attempt_id"] == running and not view[first].get("attempt_id"), "der erste bleibt frei für „Los“"
    paper(second, "graded", at(MON, 16))
    checked = {s["topic_id"]: s["done"] for s in sp.mark_done(1, steps, MON) if s.get("format") == "kurz"}
    assert checked == {first: False, second: True}, "erledigt ist der Schritt, zu dem die Arbeit passt"


def test_entry_test_calibrates_and_the_day_only_shrinks(world):
    """D192: Solange der Einstiegstest aussteht, warten die übrigen Schritte der
    Arbeit; danach entfällt, was er schon zeigt. Die Liste wächst nie."""
    ids = exam("ma", "Mathematik", MON + timedelta(days=1), ["Terme", "Gleichungen"])
    steps = sp.ensure(1, MON)
    assert [(s["kind"], s["format"]) for s in steps] == [("paper", "einstieg"), ("dialog", None), ("paper", "kurz"),
                                                         ("dialog", None), ("paper", "kurz"), ("paper", "probe")]
    view = sp.view(1, MON, store=True)
    assert [bool(s["waiting"]) for s in view["steps"]] == [False] + [True] * 5
    assert view["total"] == 6 and view["done"] == 0
    with closing(db.webapp_conn()) as c, c:
        eid = c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,created_at,status,exam_key,paper_format) "
                        "VALUES(1,'E','Mathematik','{}','[]',30,'t','published','ma','einstieg')").lastrowid
        aid = c.execute("INSERT INTO mentor_exam_attempts(account_id,exam_id,user_id,snapshot,started_at,status,is_test,submitted_at) "
                        "VALUES(1,?,2,'{}','t','graded',0,?)", (eid, at(MON, 16).isoformat())).lastrowid
    for afb in (1, 2):
        answer(ids[0], afb, 4, when=at(MON, 16), source="paper", fmt="einstieg", attempt=aid)
        answer(ids[1], afb, 1, when=at(MON, 16), source="paper", fmt="einstieg", attempt=aid)
    view = sp.view(1, MON, store=True)
    got = [(s["format"], s["topic_id"], s["done"], bool(s["skipped"]), bool(s["waiting"])) for s in view["steps"]]
    assert got == [("einstieg", None, True, False, False),
                   (None, ids[0], True, True, False), ("kurz", ids[0], True, True, False),
                   (None, ids[1], False, False, False), ("kurz", ids[1], False, False, False),
                   ("probe", None, False, False, False)]
    assert view["total"] == 6 and view["done"] == 3 and sp.open_count(1, MON) == 3
    assert all(s["why"].startswith("Nicht mehr nötig") for s in view["steps"] if s["skipped"])


def test_speaking_exam_is_practised_in_conversation_and_old_paper_steps_go(world):
    """D193: Bei einer Sprechprüfung nur Gesprächsschritte je Thema, kein Papier;
    schon festgehaltene Papierschritte entfallen."""
    from backend import exam_meta
    exam("en", "Englisch", MON + timedelta(days=1), ["Meine Familie", "Hobbys"])
    frozen = sp.ensure(1, MON)
    assert frozen[0]["format"] == "einstieg"
    exam_meta.remember(1, "en", "Sprechprüfung Englisch Jg.6")
    assert seq("en") == [("oral", "einstieg")], "zuerst der Einstiegstest Sprechprüfung (D195)"
    view = sp.view(1, MON, store=True)
    assert [(s["kind"], s["format"], s["title"]) for s in view["steps"]] == [("oral", "einstieg", "Einstiegstest Sprechprüfung Englisch")], \
        "schriftliche Schritte verschwinden, der Einstiegstest wird umgestellt"
    assert view["total"] == 1 and sp.open_count(1, MON) == 1


def test_speaking_exam_plans_simulations_with_a_one_day_buffer(world):
    """D194: Je Sprechthema eine Sprechprobe und eine Gesamtprobe, Puffer ein Schultag;
    erledigt ist ein Schritt mit einer ausgewerteten Probe."""
    import json as _json
    from backend import exam_meta
    ids = exam("en", "Englisch", MON + timedelta(days=3), ["Meine Familie", "Hobbys"])
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET origin='manual' WHERE exam_key='en'")  # von Eltern eingetragene Sprechthemen
    exam_meta.remember(1, "en", "Sprechprüfung Englisch")
    p = next(p for p in sp.plans(1, MON) if p["exam_key"] == "en")
    assert [(x["kind"], x["format"], x["topic_id"]) for x in p["sequence"]] == [("oral", "einstieg", None)]
    assert p["days"] == 2, "Donnerstag Prüfung, Mittwoch Puffer: Montag und Dienstag"
    steps = sp.ensure(1, MON)
    assert steps[0]["href"] == "#/learning?oral=en" and steps[0]["title"] == "Einstiegstest Sprechprüfung Englisch"
    good = _json.dumps([{"criterion": "aufgabe", "score": 2, "evidence": "x"}])
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO oral_sims(account_id,exam_key,topic_id,full,session_id,created_at,scores_json,reliable) VALUES(1,'en',NULL,1,1,?,?,1)",
                  (at(MON, 16).isoformat(), good))
    view = sp.view(1, MON, store=True)
    assert view["steps"][0]["done"] and not view["steps"][0].get("skipped")
    # Danach: je Sprechthema eine Probe und eine Gesamtprobe.
    p = next(p for p in sp.plans(1, MON) if p["exam_key"] == "en")
    assert [(x["kind"], x["topic_id"]) for x in p["sequence"]] == [("oral", ids[0]), ("oral", ids[1]), ("oral", None)]
    assert p["sequence"][0]["title"] == "Sprechprobe Englisch: Meine Familie"


def test_speaking_exam_without_own_topics_uses_the_taught_grammar_only_as_reference(world):
    """D195: Ohne eingetragene Sprechthemen treten die Themen aus dem Unterricht
    zurück; der Plan kennt die Prüfung trotzdem und beginnt mit dem Einstiegstest."""
    from backend import exam_meta, lernstand
    exam_meta.remember(1, "en", "Sprechprüfung Englisch")
    mentor_opening.remember_exam(1, "en", (MON + timedelta(days=3)).isoformat())
    scope = {"topics": [{"title": "Simple past", "field": "Vergangenheit", "lesson_ids": []}]}
    lernstand.ensure_assumed_topics(1, "en", "Englisch", scope)
    with closing(db.webapp_conn()) as c:
        assert [tuple(r) for r in c.execute("SELECT title,origin,stale FROM exam_topics WHERE exam_key='en'")] == [("Simple past", "assumed", 1)]
    assert seq("en") == [("oral", "einstieg")]


def test_the_friday_list_stays_on_the_weekend_and_weekend_work_counts(world, monkeypatch):
    """D205: Am freien Tag kein neues Pensum, aber die Liste des letzten Schultags
    bleibt bis Sonntagabend stehen; was am Wochenende erledigt wird, zählt für sie."""
    FRI, SUN = MON + timedelta(days=4), MON + timedelta(days=6)
    ids = exam("ma", "Mathematik", MON + timedelta(days=8), ["Terme"])
    answer(ids[0], 1, 1, when=at(MON, 10), source="paper")  # gemessen, Terme wackeln
    friday = sp.ensure(1, FRI)
    assert friday and friday[0]["kind"] == "dialog"
    kid = SimpleNamespace(id=2, role="child", is_admin=False)
    monkeypatch.setattr(sp.rewards, "acting_child", lambda user: True)
    sat = sp.today(1, kid, at(SAT, 10))
    assert sat["day"] == FRI.isoformat() and sat["carry"] == {"from": FRI.isoformat(), "until": SUN.isoformat(), "open": len(friday)}
    assert [s["key"] for s in sat["steps"]] == [s["key"] for s in friday] and sat["free_day"]
    for k in range(3):
        answer(ids[0], 1, 3, when=at(SAT, 11, k))
    sun = sp.today(1, kid, at(SUN, 9))
    assert sun["steps"][0]["done"], "Samstag zählt für die Freitagsliste"
    # Die Familienkarte der Eltern liest dieselbe Liste mit demselben Stand
    # und hält nichts fest.
    card = sp.for_day(1, SUN, store=False)
    assert card["carry"]["from"] == FRI.isoformat()
    assert (card["done"], card["total"]) == (sun["done"], sun["total"]) and card["steps"] == sun["steps"]
    assert sp.stored(1, SUN) is None
    assert sp.open_count(1, FRI, SUN) == sun["total"] - sun["done"]
    assert "carry" not in sp.today(1, kid, at(MON + timedelta(days=7), 15)), "am Montag gilt der neue Tag"


def test_weekend_vocab_counts_for_the_friday_vocab_step(world, monkeypatch):
    import backend
    FRI = MON + timedelta(days=4)
    days = {FRI: set(range(6)), SAT: set(range(6, 12))}
    mod = types.SimpleNamespace(daily=lambda a, d: [], _unit_words=lambda a, subject, unit: list(range(20)),
                                practiced=lambda a, d, ids=None: days.get(d, set()))
    monkeypatch.setitem(sys.modules, "backend.vocab_pensum", mod)
    monkeypatch.setattr(backend, "vocab_pensum", mod, raising=False)
    step = {"kind": "vocab", "key": "vocab:Latein:u1", "subject": "Latein", "target": 10}
    assert not sp._vocab_done_since(1, step, FRI, FRI)
    assert sp._vocab_done_since(1, step, FRI, SAT)


def test_a_first_probe_is_the_entry_test_not_the_final_probe():
    """Eine Probearbeit ganz am Anfang misst den Stand; die Probearbeit am Ende,
    für die geübt wird, bleibt offen (D218)."""
    steps = [{"format": "einstieg"}, {"format": "kurz", "topic_id": 11}, {"format": "kurz", "topic_id": 12},
             {"format": "probe"}]
    probe, k11, k12 = ({"id": 3, "format": "probe", "topics": {11, 12}}, {"id": 5, "format": "kurz", "topics": {11}},
                       {"id": 6, "format": "kurz", "topics": {12}})
    assert sp._match_papers(steps, [probe, k11, k12]) == {0, 1, 2}
    later = {"id": 9, "format": "probe", "topics": {11, 12}}
    assert sp._match_papers(steps, [probe, k11, k12, later]) == {0, 1, 2, 3}
    # Ein echter Einstiegstest bleibt der Einstieg; eine Probearbeit danach ist die Probearbeit.
    entry = {"id": 2, "format": "einstieg", "topics": {11, 12}}
    assert sp._match_papers(steps, [entry, probe]) == {0, 3}
    # Ein Kurztest als erste Arbeit bleibt der Kurztest.
    assert sp._match_papers(steps, [k12]) == {2}
