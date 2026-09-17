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
    assert mopen.situation(1, {"source_json": json.dumps({"mode": "homework_check"})}, ctx)["lage"] == "kontrollieren"
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


def test_compare_endpoint_runs_each_tier_without_saving(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Verben")["id"]
    tiers = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        tiers.append(kw.get("tier"))
        return json.dumps({"message": f"Einstieg von {kw.get('tier')}", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": ""}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    s = client.post(B + "/sessions", json={"topic_id": tid}).json()
    r = client.post(B + f"/sessions/{s['id']}/opening/compare", json={"tiers": ["mittel", "niedrig"]})
    assert r.status_code == 200, r.text
    assert [x["tier"] for x in r.json()["results"]] == ["mittel", "niedrig"] and tiers[1:] == ["mittel", "niedrig"]
    assert client.get(B + f"/sessions/{s['id']}").json()["messages"][0]["text"] == "Einstieg von None"


def _missed_lesson(patch):
    """Eine versäumte Deutschstunde mit Quelle: Untis-Text nennt S. 42, das Material liegt vor."""
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("INSERT INTO lessons VALUES(2,1,'2026-09-09','07:50','08:35','Deutsch',1,1,'Satzglieder: Subjekt und Prädikat, S. 42',1,NULL)")
        c.execute("CREATE TABLE absences(account_id INTEGER,start_date TEXT,end_date TEXT,start_time TEXT,end_time TEXT,reason TEXT)")
        c.execute("INSERT INTO absences VALUES(1,'2026-09-09','2026-09-09',NULL,NULL,'Krankheit')")
    with closing(db.webapp_conn()) as c, c:
        mid = c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,source_label,source_page,analysis_state,created_at,updated_at) "
                        "VALUES(1,'book_page','Deutsch','Schulbuch S. 42','Das Subjekt ist der Satzgegenstand: Wer oder was? Das Prädikat ist die Satzaussage.','Schulbuch',42,'ready','now','now')").lastrowid
        c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,page,status,material_id,synced_at,updated_at) "
                  "VALUES(1,'lesson',2,'2026-09-09','Deutsch','Schulbuch','book',42,'ready',?,'now','now')", (mid,))
    from backend import sources
    patch.setattr(sources, "ensure_synced", lambda *a, **k: None)
    return mid


def test_a_missed_lesson_opens_as_catch_up_with_the_lessons_source(exam_env):
    client, state, patch, nid, extraction = exam_env
    mid = _missed_lesson(patch)
    seen = {}

    async def complete(account, purpose, instruction, context, *a, **kw):
        seen["instruction"] = instruction; seen["context"] = context
        return json.dumps({"message": "Am Mittwoch warst du nicht da. Es ging um Subjekt und Prädikat: Das Subjekt antwortet auf „Wer oder was?“, das Prädikat sagt, was passiert. Probier gleich eine Aufgabe.",
                           "choices": ["Erklär es ausführlicher", "Habe ich mir schon angeschaut", "Was kommt in der Hausaufgabe vor?"], "action": "task",
                           "task": {**TASK, "prompt": "Nenne Subjekt und Prädikat: Der Hund schläft."}, "assessment": None, "summary": ""}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    s = client.post(B + "/sessions", json={"subject": "Deutsch", "lesson_id": 2, "voluntary": True}).json()
    assert "Lage: Das Kind hat eine Stunde versäumt" in seen["instruction"]
    lage = seen["context"]["situation"]
    assert lage["lage"] == "nachholen" and lage["missed"] == {"date": "2026-09-09", "text": "Satzglieder: Subjekt und Prädikat, S. 42"}
    assert seen["context"]["source"]["missed"] is True and seen["context"]["source"]["missed_minutes"] == 45
    # Die Quelle der versäumten Stunde steht vorn im Material, mit Inhalt.
    assert seen["context"]["materials"][0]["id"] == mid and "Satzgegenstand" in seen["context"]["materials"][0]["inhalt"]
    assert s["situation"]["label"] == "Nachholen" and s["messages"][0]["text"].startswith("Am Mittwoch warst du nicht da")
    # Für heute fertig: die Stunde gilt als nachgeholt, mit demselben Eintrag wie der Haken in der Liste.
    done = send(client, s, kind="finish", text="Für heute fertig").json()
    assert done["status"] == "completed" and done["messages"][-1]["text"].endswith("Die Stunde vom 09.09. gilt damit als nachgeholt.")
    with closing(db.webapp_conn()) as c:
        row = c.execute("SELECT note,user_id FROM caught_up WHERE account_id=1 AND lesson_id=2").fetchone()
    assert row is not None and row["note"] == "Mit dem Mentor nachgeholt"


def test_the_mentor_closing_a_catch_up_unit_marks_the_lesson_too(exam_env):
    client, state, patch, nid, extraction = exam_env
    _missed_lesson(patch)
    patch.setattr(ai, "complete", lambda *a, **kw: _reply({"message": "Los geht es.", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": ""}))
    s = client.post(B + "/sessions", json={"subject": "Deutsch", "lesson_id": 2, "voluntary": True}).json()
    assert s["situation"]["lage"] == "nachholen"
    patch.setattr(ai, "complete", lambda *a, **kw: _reply({"message": "Das war es für heute.", "choices": [], "action": "finish", "task": None, "assessment": None, "summary": "Subjekt und Prädikat erkannt."}))
    done = send(client, s, text="Ich habe es verstanden").json()
    # Vorschlag statt Abbruch: die Stunde gilt als nachgeholt, die Einheit bleibt offen, bis das Kind entscheidet.
    assert done["status"] == "active" and "gilt damit als nachgeholt" in done["messages"][-1]["text"]
    assert done["messages"][-1]["payload"]["choices"] == ["Für heute fertig", "Noch weitermachen"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM caught_up WHERE account_id=1 AND lesson_id=2").fetchone()[0] == 1
    assert send(client, done, kind="finish").json()["status"] == "completed"
    # Eine neue Einheit zu derselben Stunde ist kein Nachholen mehr: die Stunde ist erledigt.
    patch.setattr(ai, "complete", lambda *a, **kw: _reply({"message": "Weiter.", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": ""}))
    again = client.post(B + "/sessions", json={"subject": "Deutsch", "lesson_id": 2, "voluntary": True}).json()
    assert again["situation"]["lage"] != "nachholen"


def test_a_choice_never_hands_over_the_answer():
    """Am 17.09. stand unter einer Auswahlaufgabe zum relativen Superlativ die
    richtige Lösung als antippbarer Knopf. Das Kind hat sie angetippt und der
    Mentor „Richtig“ gebucht — geübt wurde nichts (D95)."""
    from backend.routers.mentor import safe_choices
    task = {
        "prompt": "Wähle den Satz mit dem relativen Superlativ:\n"
                  "A) Nico es más fuerte que Ana.\n"
                  "B) Nico es el jugador más fuerte del equipo.\n"
                  "C) Mateo es tan alto como Nico.\nSchreibe nur A, B oder C.",
        "solution": "B", "criteria": "Richtig ist B. Ein relativer Superlativ hat Artikel und más, "
                                     "z. B. el jugador más fuerte.",
    }
    kept = safe_choices(['Erst kurz erklären', 'Nico es el jugador más fuerte', 'Weiß ich nicht'], task)
    assert kept == ['Erst kurz erklären', 'Weiß ich nicht']
    # Auch eine wörtlich abgeschriebene Antwortmöglichkeit fliegt raus.
    assert safe_choices(['Nico es más fuerte que Ana.'], task) == []
    # Ein Hinweis auf das Vorgehen bleibt.
    assert safe_choices(['Achte auf den Artikel'], task) == ['Achte auf den Artikel']
    # Ohne Aufgabe wird nichts angefasst.
    assert safe_choices(['Egal was'], None) == ['Egal was']
    # Kurze Marken wie „A“ oder „Los“ bleiben, sie verraten nichts.
    assert safe_choices(['Los', 'B'], task) == ['Los', 'B']


def test_the_guard_also_covers_a_normal_turn(setup):
    """Nicht nur der Einstieg: Auch ein Zug mitten in der Einheit darf die
    Lösung nicht als Knopf anbieten."""
    from backend.routers.mentor import safe_choices
    import json as _json
    task = _json.dumps({"prompt": "Bilde den Satz.", "solution": "la ciudad más famosa",
                        "criteria": "Der Satz enthält „la ciudad más famosa“."})
    assert safe_choices(['la ciudad más famosa', 'Erst kurz erklären'], task) == ['Erst kurz erklären']
