"""Der Einstieg in eine Einheit: Lage erkannt, erster Zug vom Modell, Schlusssatz mit Stufe."""
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path  # noqa: F401
from test_mentor import setup, send, B, TASK  # noqa: F401
from test_lernstand import exam_env, topic_reply  # noqa: F401
from backend import db, lernstand, mentor_opening as mopen, ai_gateway as ai
from backend.routers import mentor as m
import pytest


@pytest.fixture(autouse=True)
def opening_on(request, monkeypatch):
    # Nach dem setup-Fixture (das den Einstieg abschaltet) wieder einschalten.
    if "exam_env" in request.fixturenames:
        request.getfixturevalue("exam_env")
    monkeypatch.setattr(m, "OPENING", True)
    from datetime import date
    monkeypatch.setattr(mopen, "today_local", lambda: date(2026, 9, 11))


def test_situation_is_read_from_entry_point_and_signals(env):
    # `situation` liest exam_topics; ohne eingerichtete Datenbank fehlte die Tabelle (CI-Fehler).
    ctx = {"lessons": [{"id": 1, "date": "2026-09-11", "text": "Adjektive", "rating": 2, "note": "", "catch_up_open": False, "missed_minutes": 0}], "topic": None}
    s = {"source_json": json.dumps({"mode": "topic"}), "topic_id": 5}
    assert mopen.situation(1, s, {**ctx, "topic": {"check": False}})["lage"] == "trainieren"
    assert mopen.situation(1, s, {**ctx, "topic": {"check": True}})["lage"] == "pruefen"
    assert mopen.situation(1, {"source_json": json.dumps({"mode": "homework_help"})}, ctx)["lage"] == "begleiten"
    lesson = mopen.situation(1, {"source_json": json.dumps({"lesson_id": 1})}, ctx)
    assert lesson["lage"] == "erklaeren" and lesson["feedback"]["rating"] == 2
    missed = {**ctx, "lessons": [{**ctx["lessons"][0], "rating": None, "catch_up_open": True}]}
    assert mopen.situation(1, {"source_json": json.dumps({"lesson_id": 1})}, missed)["lage"] == "nachholen"
    fine = {**ctx, "lessons": [{**ctx["lessons"][0], "rating": 3}]}
    assert mopen.situation(1, {"source_json": json.dumps({"lesson_id": 1})}, fine)["lage"] == "trainieren"
    assert mopen.situation(1, {"source_json": "{}"}, fine)["lage"] == "frei"
    # Ohne Anlass, aber mit schlechter Rückmeldung im Fach: erklären.
    assert mopen.situation(1, {"source_json": "{}"}, ctx)["lage"] == "erklaeren"


def test_closing_sentence_names_stage_reason_and_next_check():
    assert mopen.closing_sentence({"stage": "sitzt", "reason": "3 Aufgaben in 2 Arten", "next_check": "2026-09-19"}).startswith(
        "Stand jetzt: sitzt (3 Aufgaben in 2 Arten). Ab 19.09. frage ich es noch einmal kurz ab")
    assert "genau da an" in mopen.closing_sentence({"stage": "wackelt", "reason": "1× erst mit Hinweis richtig"})
    assert mopen.closing_sentence({"stage": "neu", "reason": ""}) == "Stand jetzt: neu."


def test_opening_uses_the_topic_material_and_the_exam_date(exam_env):
    client, state, patch, nid, extraction = exam_env
    mopen.remember_exam(1, "cal:latein-2026-09-21", "2026-09-21")
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "a-/o-Deklination")["id"]
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET places_json=?,note='Genitiv Plural zweimal falsch' WHERE id=?", (json.dumps([{"label": "Begleitband", "pages": [13]}]), tid))
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,source_label,source_page,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','Latein','BB 13','Die a-Deklination: serva, servae … Die o-Deklination: servus, servi …','Begleitband',13,'ready','now','now')")
    seen = {}

    async def complete(account, purpose, instruction, context, *a, **kw):
        seen["purpose"] = purpose; seen["instruction"] = instruction; seen["context"] = context; seen["model"] = kw.get("model")
        return json.dumps({"message": "Montag ist die Lateinarbeit. Thema 2: a-/o-Deklination, Begleitband S. 13. Letztes Mal war der Genitiv Plural wacklig, da fangen wir an.",
                           "choices": ["Erst kurz erklären", "Lieber Singular zuerst", "Weiß ich nicht"], "action": "task",
                           "task": {**TASK, "operator": "Bilde", "prompt": "Bilde den Genitiv Plural von servus."}, "assessment": None, "summary": ""}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    s = client.post(B + "/sessions", json={"topic_id": tid}).json()
    assert seen["purpose"] == "opening" and "Lerncoach" in seen["instruction"] and "Lage: Das Kind bereitet eine Arbeit vor" in seen["instruction"]
    assert seen["context"]["situation"]["lage"] == "trainieren" and seen["context"]["situation"]["exam"]["date"] == "2026-09-21"
    assert seen["context"]["situation"]["exam"]["days"] == 10
    assert "a-Deklination" in seen["context"]["topic"]["material"][0]["text"] and seen["context"]["topic"]["note"] == "Genitiv Plural zweimal falsch"
    assert s["messages"][0]["text"].startswith("Montag ist die Lateinarbeit") and s["messages"][0]["payload"]["choices"][0] == "Erst kurz erklären"
    assert s["task"]["prompt"] == "Bilde den Genitiv Plural von servus." and "solution" not in s["task"]
    assert s["situation"] == {"lage": "trainieren", "label": "Arbeit vorbereiten", "why": "Thema der offiziellen Themenliste", "exam": {"date": "2026-09-21", "days": 10}}
    # Eine Erklärung vor der ersten Antwort ist keine Hilfe; die Antwort danach zählt sauber.
    patch.setattr(ai, "complete", lambda *a, **kw: _reply(topic_reply("Bilde", None, action="explain")))
    s2 = send(client, s, kind="hint", text="Erst kurz erklären").json()
    with closing(db.webapp_conn()) as c:
        assert tuple(c.execute("SELECT help_count,task_help FROM mentor_sessions WHERE id=?", (s["id"],)).fetchone()) == (1, 1)
    # (Hier war eine Aufgabe offen: zählt.) Ohne offene Aufgabe zählt Erklären nicht.
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_sessions SET current_task=NULL,task_help=0,help_count=0 WHERE id=?", (s["id"],))
    s2 = client.get(B + f"/sessions/{s['id']}").json()
    s3 = send(client, s2, kind="hint", text="Erklär es noch einmal").json()
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT help_count FROM mentor_sessions WHERE id=?", (s["id"],)).fetchone()[0] == 0


async def _reply(payload):
    return json.dumps(payload), {}, "fake"


def test_opening_falls_back_to_the_fixed_greeting_when_the_model_fails(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Verben")["id"]

    async def boom(*a, **kw):
        raise RuntimeError("Netz weg")
    patch.setattr(ai, "complete", boom)
    s = client.post(B + "/sessions", json={"topic_id": tid}).json()
    assert s["status"] == "active" and s["messages"][0]["text"].startswith("Wir nehmen uns „Verben“ vor") and s["task"] is None


def test_finish_by_button_ends_a_topic_unit_with_the_stage_sentence(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Verben")["id"]

    async def boom(*a, **kw):
        raise RuntimeError("Netz weg")
    patch.setattr(ai, "complete", boom)
    s = client.post(B + "/sessions", json={"topic_id": tid}).json()
    s = send(client, s, kind="finish", text="Für heute fertig.").json()
    assert s["status"] == "completed" and s["messages"][-1]["text"].endswith("Stand jetzt: neu.")


def test_compare_endpoint_runs_each_model_without_saving(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Verben")["id"]
    models = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        models.append(kw.get("model"))
        return json.dumps({"message": f"Einstieg von {kw.get('model')}", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": ""}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    s = client.post(B + "/sessions", json={"topic_id": tid}).json()
    r = client.post(B + f"/sessions/{s['id']}/opening/compare", json={"models": ["gpt-5.6-terra", "gpt-5.6-luna"]})
    assert r.status_code == 200, r.text
    assert [x["model"] for x in r.json()["results"]] == ["gpt-5.6-terra", "gpt-5.6-luna"] and models[1:] == ["gpt-5.6-terra", "gpt-5.6-luna"]
    assert client.get(B + f"/sessions/{s['id']}").json()["messages"][0]["text"] == "Einstieg von None"
