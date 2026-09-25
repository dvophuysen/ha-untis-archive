"""Lernen als Kompass (D186): ein Aufruf liefert nächste Arbeit mit Einschätzung,
die Pflicht aus dem Tagesplan, Stärken und Baustellen, Extra, Verlauf je Woche,
offene Einheiten, frühere Arbeiten und das Archiv."""
import asyncio
import json
from contextlib import closing
from datetime import timedelta
from types import SimpleNamespace

import pytest

from test_learning import env, child  # noqa: F401
from test_study_plan import world, exam, answer, ready, at, vocab, MON, KID, PARENT  # noqa: F401
from backend import db, exams as exams_mod, learning_compass as lc, study_plan as sp


@pytest.fixture
def compass(world, monkeypatch):
    async def no_calendar(*a, **kw):
        return {"exams": []}
    monkeypatch.setattr(exams_mod, "resolve_exams", no_calendar)

    def run(user=KID, when=None):
        return asyncio.run(lc.build(1, user, when or at(MON, 15)))
    return run


def rate(lesson_day, rating):
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,?,2,?,'t','t')",
                  (int(lesson_day.strftime("%Y%m%d")), rating))


def session(goal, topic=None, updated=None, mode="practice", status="active"):
    updated = updated or at(MON, 9).isoformat()
    with closing(db.webapp_conn()) as c, c:
        return c.execute("INSERT INTO mentor_sessions(account_id,user_id,subject,goal,status,phase,source_json,created_at,updated_at,is_test,topic_id) "
                         "VALUES(1,2,'Mathematik',?,?,'clarify',?,?,?,0,?)",
                         (goal, status, json.dumps({"mode": mode}), updated, updated, topic)).lastrowid


def test_next_exam_with_verdict(compass):
    d = compass()
    assert d["next_exam"] is None and d["calm"]["text"].startswith("Keine Arbeit in Sicht")
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme", "Gleichungen"])
    d = compass()
    n = d["next_exam"]
    assert (n["exam_key"], n["subject"], n["day_label"], n["school_days_left"]) == ("ma", "Mathematik", "Mi 07.10.", 7)
    # D188: 6 Schritte (Einstieg, je Thema Üben und Nachweis, Probearbeit) in 5 Lerntagen vor dem Puffer.
    assert (n["ready"], n["total"], n["verdict"]) == (0, 2, "knapp") and d["calm"] is None
    assert n["verdict_text"] == "Knapp: noch etwa 6 Schritte in 5 Lerntagen. Jeden Tag dranbleiben."
    assert [p["state"] for p in n["path"]] == ["now", "todo", "todo", "todo"] and n["stage"] == "einstieg"
    assert [t["state"] for t in n["raster"]] == ["neu", "neu"]
    ready(ids[0])
    n = compass()["next_exam"]
    assert n["ready"] == 1 and n["stage"] == "luecken" and [t["state"] for t in n["raster"]] == ["sitzt", "neu"]
    # Die nächste Arbeit mit Themen zuerst; reichen die Schultage vor dem Puffer nicht: eng.
    exam("en", "Englisch", MON + timedelta(days=4), ["A", "B", "C"])
    n = compass()["next_exam"]
    assert (n["exam_key"], n["school_days_left"], n["verdict"]) == ("en", 4, "eng")
    exam("bi", "Biologie", MON + timedelta(days=2), ["A", "B"])
    n = compass()["next_exam"]
    assert (n["exam_key"], n["school_days_left"], n["verdict"]) == ("bi", 2, "eng")
    assert [e["exam_key"] for e in compass()["exams"]] == ["bi", "en", "ma"]


def test_plan_is_the_study_plan(compass):
    exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    d = compass(KID)
    assert d["plan"]["steps"] == sp.view(1, MON, store=False)["steps"]
    assert d["plan"]["steps"][0]["format"] == "einstieg" and d["plan"]["frozen"], "das Kind friert den Plan ein wie auf Heute"
    assert len(d["plan_explain"]) == 3


def test_strengths_and_gaps(compass):
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme", "Gleichungen", "Brüche"])
    ready(ids[1], when=at(MON - timedelta(days=3), 10))
    answer(ids[0], 1, 1, source="paper"); answer(ids[0], 1, 0, source="paper")
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET stage='wackelt' WHERE id=?", (ids[2],))
    rate(MON - timedelta(days=3), 1)
    rate(MON - timedelta(days=4), 2)
    rate(MON - timedelta(days=20), 1)  # zu alt
    d = compass()
    s = d["strengths"]
    assert s[0]["kind"] == "topic" and s[0]["title"] == "Gleichungen" and s[0]["text"].startswith("sicher seit")
    g = d["gaps"]
    assert [(x["kind"], x["title"]) for x in g] == [("topic", "Terme"), ("topic", "Brüche"), ("lessons", "Kommasetzung")]
    assert g[0]["href"] == f"#/learning?topic_id={ids[0]}" and "Wiedergeben ist noch unsicher" in g[0]["why"]
    assert g[2]["href"].startswith("#/learning?lesson_id=") and "subject=Deutsch" in g[2]["href"]
    assert len(g) <= 3 and len(s) <= 3
    # Eine einzelne 😐 macht noch keine Baustelle.
    with closing(db.webapp_conn()) as c, c:
        c.execute("DELETE FROM lesson_checkins WHERE rating=1")
    assert [x["kind"] for x in compass()["gaps"]] == ["topic", "topic"]


def test_cell_strength_without_whole_topic(compass):
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    for _ in range(2):
        answer(ids[0], 1, 4, when=at(MON - timedelta(days=1), 10))
    d = compass()
    assert d["strengths"] == [{"kind": "cell", "topic_id": ids[0], "subject": "Mathematik", "title": "Terme",
                               "text": "Wiedergeben sicher seit 27.09."}]
    assert d["history"]["topics"] == 0 and d["history"]["cells"] == 1
    assert d["history"]["sentence"].startswith("Noch kein Thema ganz sicher, aber 1 Bereich")


def test_history_per_week(compass):
    ma = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme", "Gleichungen"])
    la = exam("la", "Latein", MON + timedelta(days=12), ["Deklination", "Konjugation", "AcI"])
    ready(ma[0], when=at(MON - timedelta(days=6), 10))
    ready(la[0], when=at(MON - timedelta(days=13), 10))
    ready(la[1], when=at(MON, 9))
    ready(la[2], when=at(MON - timedelta(days=40), 10))  # vor dem Zeitraum sicher geworden
    h = compass()["history"]
    assert [w["label"] for w in h["weeks"]] == ["vor 3 Wochen", "vor 2 Wochen", "letzte Woche", "diese Woche"]
    assert [w["topics"] for w in h["weeks"]] == [0, 1, 1, 1]
    assert h["sentence"] == "3 Themen sind sicher geworden, 2 davon in Latein."
    # Ein Stufenwechsel auf „sitzt“ zählt wie das Raster, das Thema nur einmal.
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO topic_events(account_id,topic_id,stage_before,stage_after,reason,created_at) VALUES(1,?,'wackelt','sitzt','x',?)",
                  (ma[1], at(MON - timedelta(days=1), 10).isoformat()))
        c.execute("INSERT INTO topic_events(account_id,topic_id,stage_before,stage_after,reason,created_at) VALUES(1,?,'wackelt','sitzt','x',?)",
                  (ma[0], at(MON - timedelta(days=2), 10).isoformat()))
    h = compass()["history"]
    assert [w["topics"] for w in h["weeks"]] == [0, 1, 2, 1]


def test_past_exams_show_state_at_the_time_and_archive(compass):
    past = exam("de", "Deutsch", MON - timedelta(days=3), ["Nominalisierung"])
    ready(past[0], when=at(MON - timedelta(days=5), 10))
    for _ in range(4):
        answer(past[0], 1, 0, when=at(MON - timedelta(days=1), 10))  # nach der Arbeit: zählt nicht
    ids = exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    old = session("Vorbereitung", topic=past[0], updated=at(MON - timedelta(days=4), 10).isoformat())
    fresh = [session(f"Frisch {i}", updated=at(MON, 8, i).isoformat()) for i in range(4)]
    session("Beendet", status="completed")
    d = compass()
    assert [(p["exam_key"], p["ready"], p["total"], p["raster"][0]["state"]) for p in d["past_exams"]] == [("de", 1, 1, "sitzt")]
    assert d["past_exams"][0]["day_label"] == "Fr 25.09."
    assert [s["id"] for s in d["sessions"]] == fresh[::-1][:3], "höchstens drei offene, neueste zuerst"
    assert [(s["id"], s["archive_reason"]) for s in d["archived_sessions"]] == [(old, "Arbeit am 25.09. geschrieben")]
    assert ids


def test_vocab_test_and_missing_lesson(compass, monkeypatch):
    exam("en", "Englisch", MON + timedelta(days=5), ["Vokabeln Unit 2"])
    from backend import vocab_pensum
    monkeypatch.setattr(vocab_pensum, "trainer_unit", lambda a, s, p: None, raising=False)
    d = compass()
    e = d["exams"][0]
    assert e["kind"] == "vokabeltest" and e["vocab"]["missing"] and e["total"] == 0
    assert d["next_exam"]["exam_key"] == "en"
    vocab(monkeypatch, [{"subject": "Englisch", "unit": "u2", "unit_label": "Unit 2", "target": 20, "practiced": 5,
                         "done": False, "href": "#/vokabeln/Englisch?unit=u2", "exam_key": "en", "why": "Test am Montag."}])
    e = compass()["exams"][0]
    assert e["vocab"] == {"unit": "Unit 2", "target": 20, "practiced": 5, "done": False, "href": "#/vokabeln/Englisch?unit=u2", "missing": False}


def test_extra_subjects_and_recent_topics(compass):
    exam("de", "Deutsch", MON + timedelta(days=9), ["Kommas"])
    x = compass()["extra"]
    assert [s["label"] for s in x] == ["Deutsch"]
    assert x[0]["exam_key"] == "de" and not x[0]["language"]
    assert [r["title"] for r in x[0]["recent"]] == ["Kommasetzung"], "gleiche Stunde nur einmal"
    assert x[0]["recent"][0]["href"].startswith("#/learning?lesson_id=")


def test_calendar_exam_without_topics_is_listed(compass, monkeypatch):
    async def calendar(*a, **kw):
        return {"exams": [{"exam_key": "cal:1", "date": (MON + timedelta(days=6)).isoformat(), "subject_name": "Physik", "title": "Test Physik"}]}
    monkeypatch.setattr(exams_mod, "resolve_exams", calendar)
    d = compass()
    assert [(e["exam_key"], e["subject"], e["topics_missing"]) for e in d["exams"]] == [("cal:1", "Physik", True)]
    assert d["next_exam"] is None, "ohne Themen keine Einschätzung"
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT exam_date FROM exam_dates WHERE exam_key='cal:1'").fetchone()[0] == (MON + timedelta(days=6)).isoformat()


def test_endpoint_is_light_and_read_only_for_mirror(env, compass, monkeypatch):
    from backend.routers import compass as routes, learning as learning_routes
    from backend import rewards
    client, state, _ = env
    client.app.include_router(routes.router, prefix="/api")
    monkeypatch.setattr(rewards, "now_local", lambda: at(MON, 15))

    def boom(*a, **kw):
        raise AssertionError("kein schwerer Aufruf")
    monkeypatch.setattr(learning_routes, "overview", boom)
    exam("ma", "Mathematik", MON + timedelta(days=9), ["Terme"])
    child(state)
    r = client.get("/api/accounts/1/learning/compass")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["can_write"] and not d["can_manage"] and d["next_exam"]["exam_key"] == "ma"
    assert set(d) >= {"plan", "exams", "strengths", "gaps", "extra", "history", "sessions", "past_exams", "archived_sessions"}
    assert client.get("/api/accounts/2/learning/compass").status_code == 403
