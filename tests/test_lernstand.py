"""Lernstand: Stufen je Thema der offiziellen Themenliste, aus Antworten abgelesen."""
import json
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path  # noqa: F401
from test_mentor import setup, mock, send, B, TASK  # noqa: F401
from backend import db, lernstand, ai_gateway as ai
from backend.routers import exams as exams_router


def answer(session, day, result="correct", help_used=False, seconds=8, edits=0, kind="Bilde",
           re_explained=False, afb=2, form="kurz"):
    # afb 2 als Vorgabe: die üblichen Übungsaufgaben sind Anwenden. „Sitzt“
    # verlangt mindestens eine davon (D97), reines Wiedergeben genügt nicht.
    return dict(session_id=session, created_at=f"{day}T15:00:00+02:00", result=result, help_used=int(help_used),
                seconds=seconds, edits=edits, task_kind=kind, re_explained=int(re_explained),
                afb=afb, task_form=form)


def test_three_clean_answers_in_two_kinds_mean_sitzt():
    rows = [answer(1, "2026-09-16", kind="Bilde"), answer(1, "2026-09-16", kind="Erkenne"), answer(1, "2026-09-16", kind="Übersetze")]
    state = lernstand.replay(rows)
    assert state["stage"] == "sitzt" and state["sat_at"] == "2026-09-16" and state["next_check"] == "2026-09-19"


def test_one_kind_alone_or_hesitation_or_help_stays_wackelt():
    same_kind = [answer(1, "2026-09-16") for _ in range(4)]
    assert lernstand.replay(same_kind)["stage"] == "wackelt"
    assert "eine Aufgabenart" in lernstand.replay(same_kind)["reason"]
    slow = [answer(1, "2026-09-16", kind="Bilde"), answer(1, "2026-09-16", kind="Erkenne", seconds=70), answer(1, "2026-09-16", kind="Übersetze")]
    assert lernstand.replay(slow)["stage"] == "wackelt" and "gezögert" in lernstand.replay(slow)["reason"]
    helped = [answer(1, "2026-09-16", help_used=True)]
    assert lernstand.replay(helped)["stage"] == "wackelt" and "Hinweis" in lernstand.replay(helped)["reason"]


def test_only_wrong_or_re_explained_is_angefangen():
    rows = [answer(1, "2026-09-16", result="incorrect"), answer(1, "2026-09-16", result="partial")]
    state = lernstand.replay(rows)
    assert state["stage"] == "angefangen" and "falsch" in state["reason"]
    rows.append(answer(1, "2026-09-16", re_explained=True))
    assert lernstand.replay(rows)["stage"] == "wackelt"


def test_checks_after_three_and_seven_days_make_gefestigt_and_help_drops_back():
    sat = [answer(1, "2026-09-10", kind="Bilde"), answer(1, "2026-09-10", kind="Erkenne"), answer(1, "2026-09-10", kind="Übersetze")]
    first = [answer(2, "2026-09-13", kind="Bilde"), answer(2, "2026-09-13", kind="Erkenne")]
    state = lernstand.replay(sat + first)
    assert state["stage"] == "sitzt" and state["checks"] == 1 and state["next_check"] == "2026-09-17"
    second = [answer(3, "2026-09-17", kind="Bilde"), answer(3, "2026-09-17", kind="Übersetze")]
    assert lernstand.replay(sat + first + second)["stage"] == "gefestigt"
    # Eine Prüfung mit Hilfe setzt zurück, auch von gefestigt.
    later = [answer(4, "2026-09-25", help_used=True)]
    state = lernstand.replay(sat + first + second + later)
    assert state["stage"] == "wackelt" and state["reason"].startswith("bei der Prüfung") and state["sat_at"] is None
    # Eine einzelne saubere Antwort Tage später ist keine Prüfung und ändert nichts.
    assert lernstand.replay(sat + [answer(2, "2026-09-13", kind="Bilde")])["stage"] == "sitzt"


def test_sorting_puts_wobblers_and_the_childs_doubt_first():
    topics = [dict(stage="sitzt", position=0, next_check=None), dict(stage="neu", position=1, self_view="unsicher"),
              dict(stage="neu", position=2), dict(stage="wackelt", position=3), dict(stage="sitzt", position=4, next_check="2026-09-10")]
    order = sorted(topics, key=lambda t: lernstand.sort_key(t, date(2026, 9, 16)))
    assert [t["position"] for t in order] == [3, 4, 1, 2, 0]


NOTICE = "Latein Arbeit: Vokabeln Lektion 1 (Begleitband S. 10-11); a-/o-Deklination Begleitband S. 13; Text Gefahr im Circus Maximus Textband S. 10, 11"
EXAMS = {"exams": [{"exam_key": "cal:latein-2026-09-21", "subject_name": "Latein", "date": "2026-09-21", "title": "Latein"}], "calendar_error": None}


def notice(client_conn, account=1):
    client_conn.execute(
        "INSERT INTO materials(account_id,kind,subject_name,title,summary,content_text,document_date,created_at,updated_at,hidden,verified,source_label) "
        "VALUES(?,'exam_notice','Latein','Themenliste','', ?, '2026-09-10','2026-09-10T10:00:00','2026-09-10T10:00:00',0,1,'')", (account, NOTICE))
    return client_conn.execute("SELECT id FROM materials WHERE kind='exam_notice'").fetchone()[0]


@pytest.fixture
def exam_env(setup):
    client, state, patch = setup
    client.app.include_router(exams_router.router, prefix="/api")

    async def exams(account_id, **kw):
        return EXAMS
    patch.setattr(exams_router, "resolve_exams", exams)
    patch.setattr("backend.exams.resolve_exams", exams)
    patch.setattr(exams_router, "practice_by_subject", lambda account_id, days=28: {})
    patch.setattr(exams_router, "exam_scope", lambda *a, **k: None)
    patch.setattr("backend.sources.exam_sources", lambda *a, **k: None)
    patch.setattr("backend.erlass.resolve_section", lambda account_id, override=None: (None, None, None))
    patch.setattr(lernstand, "now_iso", lambda: "2026-09-11T15:00:00+02:00")
    patch.setattr(lernstand, "today_local", lambda: date(2026, 9, 11))
    with closing(db.webapp_conn()) as c, c:
        nid = notice(c)
    extraction = {"topics": [
        {"title": "Vokabeln Lektion 1", "detail": "Die Vokabeln der ersten Lektion.", "places": [{"label": "Begleitband", "pages": [10, 11]}]},
        {"title": "a-/o-Deklination", "detail": "Substantive der a- und o-Deklination.", "places": [{"label": "Begleitband", "pages": [13]}]},
        {"title": "Text: Gefahr im Circus Maximus", "detail": "Der Lektionstext.", "places": [{"label": "Textband", "pages": [10, 11, 99]}]},
    ]}
    return client, state, patch, nid, extraction


def test_topics_come_from_the_notice_once_and_keep_their_stage(exam_env):
    client, state, patch, nid, extraction = exam_env
    calls = []
    mock(patch, [extraction], calls)
    r = client.get("/api/accounts/1/exams/all")
    assert r.status_code == 200, r.text
    exam = r.json()["upcoming"][0]
    titles = [t["title"] for t in exam["topics"]]
    assert titles == ["Vokabeln Lektion 1", "a-/o-Deklination", "Text: Gefahr im Circus Maximus"]
    assert exam["stages"] == {"neu": 3, "angefangen": 0, "wackelt": 0, "sitzt": 0, "gefestigt": 0}
    # Seite 99 steht nicht auf dem Zettel: verworfen. Das Material fehlt komplett.
    text_topic = exam["topics"][2]
    assert text_topic["places"] == [{"label": "Textband", "pages": [10, 11]}]
    assert text_topic["material"] == {"total": 2, "have": 0, "missing": [{"label": "Textband", "pages": [10, 11], "pages_label": "S. 10–11"}], "missing_label": "Textband S. 10–11"}
    assert len(calls) == 1
    # Zweiter Aufruf: gleicher Text, kein zweiter Modellaufruf.
    client.get("/api/accounts/1/exams/all")
    assert len(calls) == 1
    # Das Kind sagt „unsicher": sortiert nach vorn, ändert die Stufe nicht.
    tid = exam["topics"][1]["id"]
    r = client.post(f"/api/accounts/1/exams/topics/{tid}/self-view", json={"value": "unsicher"})
    assert r.status_code == 200 and r.json()["self_view"] == "unsicher" and r.json()["stage"] == "neu"
    assert client.get("/api/accounts/1/exams/all").json()["upcoming"][0]["topics"][0]["id"] == tid
    # Berichtigter Zettel: gleicher Titel behält Stufe und Gefühl, verschwundenes Thema ohne Antworten geht.
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE materials SET content_text=? WHERE id=?", (NOTICE + " und Subjekt im Prädikat", nid))
    changed = {"topics": extraction["topics"][:2] + [{"title": "Subjekt im Prädikat", "detail": "", "places": []}]}
    mock(patch, [changed], calls)
    topics = client.get("/api/accounts/1/exams/all").json()["upcoming"][0]["topics"]
    assert {t["title"] for t in topics} == {"Vokabeln Lektion 1", "a-/o-Deklination", "Subjekt im Prädikat"}
    assert next(t for t in topics if t["id"] == tid)["self_view"] == "unsicher"


def test_manual_topic_and_parent_delete(exam_env):
    client, state, patch, nid, extraction = exam_env
    r = client.post("/api/accounts/1/exams/topics", json={"exam_key": "cal:latein-2026-09-21", "subject": "Latein", "title": "Zahlwörter"})
    assert r.status_code == 201 and r.json()["origin"] == "manual" and r.json()["stage"] == "neu"
    assert client.post("/api/accounts/1/exams/topics", json={"exam_key": "cal:latein-2026-09-21", "subject": "Latein", "title": "Zahlwörter"}).status_code == 409
    assert client.delete(f"/api/accounts/1/exams/topics/{r.json()['id']}").status_code == 200


def topic_reply(task_operator, result, action="task", re_explained=False, summary="Formen der a-Deklination sicher, o-Deklination mit Hinweis."):
    task = {**TASK, "operator": task_operator, "prompt": f"{task_operator} den Plural von servus ({result})."}
    return {"message": "Weiter.", "choices": [], "action": action, "task": task if action == "task" else None,
            "assessment": {"result": result, "rationale": "Begründet."} if result else None, "summary": summary, "re_explained": re_explained}


def test_topic_unit_has_no_clock_and_ends_with_the_stage(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "a-/o-Deklination")["id"]
    contexts = []
    instructions = []

    def mock(patch, outputs, contexts):
        async def complete(account, purpose, instruction, context, *args, **kw):
            contexts.append(context)
            instructions.append(instruction)
            return json.dumps(outputs[0]), {}, "fake"
        patch.setattr(ai, "complete", complete)
    mock(patch, [topic_reply("Bilde", None)], contexts)
    r = client.post(B + "/sessions", json={"subject": "Latein", "topic_id": tid})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["untimed"] and s["mode"] == "topic" and s["topic"]["title"] == "a-/o-Deklination" and s["topic"]["stage"] == "neu"
    assert s["topic"]["position"] == 1 and s["topic"]["total"] == 1 and not s["topic"]["check"]
    assert s["messages"][0]["text"].startswith("Wir nehmen uns „a-/o-Deklination“ vor")
    # Dieselbe Themen-Einheit wird wieder aufgenommen, nicht verdoppelt.
    assert client.post(B + "/sessions", json={"subject": "Latein", "topic_id": tid}).json()["id"] == s["id"]
    # Erste Aufgabe stellen.
    s = send(client, s, text="Gleich eine Aufgabe").json()
    assert s["task"]["operator"] == "Bilde"
    assert contexts[-1]["topic"]["title"] == "a-/o-Deklination" and contexts[-1]["topic"]["reached"] == "neu"
    assert "keine Uhr" in instructions[-1] and instructions[-1].rstrip().endswith("}")
    # Drei saubere Antworten in drei Arten: sitzt. Der Mentor bekommt reached=sitzt und schließt ab.
    for op, nxt in (("Bilde", "Erkenne"), ("Erkenne", "Übersetze")):
        mock(patch, [topic_reply(nxt, "correct")], contexts)
        s = send(client, s, kind="answer", text="servi", seconds=6, edits=0).json()
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT stage,reason FROM exam_topics WHERE id=?", (tid,)).fetchone()[0] == "wackelt"
    mock(patch, [topic_reply("Wende an", "correct")], contexts)
    s = send(client, s, kind="answer", text="servos", seconds=5).json()
    assert s["topic"]["stage"] == "sitzt" and s["status"] == "active"
    assert contexts[-1]["topic"]["this_unit"]["clean"] == 2
    mock(patch, [topic_reply("", "correct", action="finish")], contexts)
    s = send(client, s, kind="answer", text="servorum", seconds=4).json()
    assert contexts[-1]["topic"]["reached"] == "sitzt"
    # Der Mentor schlägt das Ende vor, beendet aber nicht: Stufe im Satz, Frage, Kind entscheidet (D73).
    assert s["status"] == "active" and s["topic"]["stage"] == "sitzt" and s["topic"]["next_check"] == "2026-09-14"
    assert "Stand jetzt: sitzt" in s["messages"][-1]["text"] and s["messages"][-1]["text"].endswith("Willst du hier aufhören oder noch eine Aufgabe?")
    assert s["messages"][-1]["payload"]["choices"] == ["Für heute fertig", "Noch eine Aufgabe"] and s["task"] is None
    with closing(db.webapp_conn()) as c:
        topic = dict(c.execute("SELECT * FROM exam_topics WHERE id=?", (tid,)).fetchone())
        events = [tuple(r) for r in c.execute("SELECT stage_before,stage_after FROM topic_events WHERE topic_id=? ORDER BY id", (tid,))]
    assert topic["note"].startswith("Formen der a-Deklination") and topic["reason"].startswith("4 Aufgaben in 4 Arten")
    assert events == [("neu", "wackelt"), ("wackelt", "sitzt")]
    # Zwölf Züge oder Minuten beenden eine Themen-Einheit nicht.
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_sessions SET status='active',turns=14,elapsed_seconds=5000 WHERE id=?", (s["id"],))
    s = client.get(B + f"/sessions/{s['id']}").json()
    mock(patch, [topic_reply("Bilde", None)], contexts)
    assert send(client, s, text="Noch eine").json()["status"] == "active"


def test_topic_instruction_and_check_mode(exam_env):
    client, state, patch, nid, extraction = exam_env
    tid = lernstand.add_manual(1, "cal:latein-2026-09-21", "Latein", "Vokabeln Lektion 1")["id"]
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET stage='sitzt',sat_at='2026-09-06',next_check='2026-09-09' WHERE id=?", (tid,))
    seen = {}

    async def complete(account, purpose, instruction, context, *args, **kw):
        seen["instruction"] = instruction
        seen["context"] = context
        return json.dumps(topic_reply("Nenne", None)), {}, "fake"
    patch.setattr(ai, "complete", complete)
    s = client.post(B + "/sessions", json={"subject": "Latein", "topic_id": tid}).json()
    assert s["topic"]["check"] and "Kurzprüfung" in s["messages"][0]["text"]
    send(client, s, text="Los")
    assert seen["context"]["topic"]["check"] is True
    assert "keine Uhr" in seen["instruction"] and "Kurzprüfung" in seen["instruction"]
    assert seen["instruction"].rstrip().endswith("}") and "re_explained" in seen["instruction"]



def test_without_a_notice_the_taught_topics_become_exam_topics_with_places(exam_env):
    client, state, patch, nid, extraction = exam_env
    with closing(db.webapp_conn()) as c, c:
        c.execute("DELETE FROM materials WHERE kind='exam_notice'")
        c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,page,quote,synced_at,updated_at) "
                  "VALUES(1,'lesson',7,'2026-09-10','Latein','Begleitband','book',13,'BB S. 13','now','now')")
        c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,page,quote,synced_at,updated_at) "
                  "VALUES(1,'homework',99,'2026-09-10','Latein','Arbeitsheft','workbook',26,'cda p. 26','now','now')")
    with sqlite3.connect(db.SETTINGS.history_db_path) as h:
        h.execute("INSERT INTO lessons(id,account_id,date,subject_name,lstext) VALUES(7,1,'2026-09-10','LATEIN','Adjektive')")
    scope = {"since": "2026-08-01", "parts": 2, "shown": 0, "verified": False, "topics": [
        {"id": 1, "title": "Adjektive und der Vergleich", "field": "Länder beschreiben", "shown": False, "lesson_ids": [7]},
        {"id": 2, "title": "Zahlen bis 1000", "field": None, "shown": False, "lesson_ids": []}]}
    patch.setattr(exams_router, "exam_scope", lambda *a, **k: scope)
    exam = client.get("/api/accounts/1/exams/all").json()["upcoming"][0]
    assert [(t["title"], t["origin"]) for t in exam["topics"]] == [("Adjektive und der Vergleich", "assumed"), ("Zahlen bis 1000", "assumed")]
    assert sorted(exam["topics"][0]["places"], key=lambda p: p["label"]) == [{"label": "Arbeitsheft", "pages": [26]}, {"label": "Begleitband", "pages": [13]}]
    assert exam["stages"]["neu"] == 2
    # Eine Einheit dazu startet wie bei einem Thema der Themenliste.
    r = client.post(B + "/sessions", json={"topic_id": exam["topics"][0]["id"]})
    assert r.status_code == 200 and r.json()["topic"]["title"] == "Adjektive und der Vergleich"
    # Kommt die Themenliste, treten die angenommenen Themen zurück.
    with closing(db.webapp_conn()) as c, c:
        notice(c)
    from test_mentor import mock
    mock(patch, [extraction], [])
    exam = client.get("/api/accounts/1/exams/all").json()["upcoming"][0]
    live = [t for t in exam["topics"] if not t["stale"]]
    assert {t["origin"] for t in live} == {"notice"} and any(t["stale"] for t in exam["topics"] if t["origin"] == "assumed")


def test_subject_overview_counts_stages_and_stage_changes_per_subject(env):
    client, state, patch = env
    with closing(db.webapp_conn()) as c, c:
        rows = [
            ("LATEIN", "cal:latein-2026-09-21", "a-/o-Deklination", "sitzt", "3 Aufgaben in 2 Arten"),
            ("LATEIN", "cal:latein-2026-09-21", "Konjugation", "wackelt", "1× erst mit Hinweis richtig"),
            ("LATEIN", "cal:latein-2026-09-21", "Ablativ", "neu", ""),
            ("Mathematik", "cal:mathe-2026-10-01", "Brüche kürzen", "gefestigt", "Prüfung nach 7 Tagen bestanden"),
            ("Mathematik", "cal:mathe-2026-10-01", "Brüche addieren", "angefangen", "zweimal falsch"),
        ]
        for i, (subject, key, title, stage, reason) in enumerate(rows, start=1):
            c.execute("INSERT INTO exam_topics(id,account_id,subject,exam_key,position,title,stage,reason,created_at,updated_at) "
                      "VALUES(?,1,?,?,?,?,?,?,'2026-09-10T10:00:00','2026-09-10T10:00:00')", (i, subject, key, i, title, stage, reason))
        # Ein altes Thema aus dem Vorjahr zählt nicht, ein veraltetes auch nicht.
        c.execute("INSERT INTO exam_topics(id,account_id,subject,exam_key,position,title,stage,created_at,updated_at) "
                  "VALUES(9,1,'LATEIN','cal:alt',9,'Vorjahr','sitzt','2026-05-01T10:00:00','2026-05-01T10:00:00')")
        c.execute("INSERT INTO exam_topics(id,account_id,subject,exam_key,position,title,stage,stale,created_at,updated_at) "
                  "VALUES(10,1,'LATEIN','cal:latein-2026-09-21',10,'Gestrichen','sitzt',1,'2026-09-10T10:00:00','2026-09-10T10:00:00')")
        events = [(1, "neu", "wackelt", "2026-09-12T15:00:00"), (1, "wackelt", "sitzt", "2026-09-14T15:00:00"),
                  (2, "sitzt", "wackelt", "2026-09-15T15:00:00"), (4, "sitzt", "gefestigt", "2026-09-15T15:00:00"),
                  (9, "neu", "sitzt", "2026-06-01T15:00:00"), (5, "neu", "angefangen", "2026-08-01T15:00:00")]
        for topic, before, after, at in events:
            c.execute("INSERT INTO topic_events(account_id,topic_id,stage_before,stage_after,reason,created_at) VALUES(1,?,?,?,'',?)",
                      (topic, before, after, at))
    view = lernstand.subject_overview(1, date(2026, 9, 16))
    assert view["since"] == "2026-08-01"
    mathe, latein = view["subjects"]
    # Stärken zuerst: Mathematik hat die Hälfte sicher, Latein ein Drittel.
    assert mathe["label"] == "Mathematik" and mathe["secure"] == 1 and mathe["total"] == 2
    assert mathe["counts"] == {"neu": 0, "angefangen": 1, "wackelt": 0, "sitzt": 0, "gefestigt": 1}
    assert mathe["trend"] == {"ups": 1, "downs": 0, "label": "aufwärts"}   # der Wechsel vom 01.08. liegt außerhalb der vier Wochen
    assert latein["label"] == "Latein" and latein["key"] == "latein" and latein["total"] == 3 and latein["secure"] == 1 and latein["wobbly"] == 1
    assert latein["trend"] == {"ups": 2, "downs": 1, "label": "aufwärts"}
    # Wackler zuerst in der Themenliste, jedes Thema mit Stufe, Grund und Arbeit.
    assert [t["title"] for t in latein["topics"]] == ["Konjugation", "Ablativ", "a-/o-Deklination"]
    assert latein["topics"][0]["label"] == "Richtig, aber nicht sicher" and latein["topics"][0]["exam_key"] == "cal:latein-2026-09-21"
    assert all("Vorjahr" != t["title"] and "Gestrichen" != t["title"] for s in view["subjects"] for t in s["topics"])
    # Ohne Wechsel im Zeitraum: kein behaupteter Verlauf.
    with closing(db.webapp_conn()) as c, c:
        c.execute("DELETE FROM topic_events")
    assert lernstand.subject_overview(1, date(2026, 9, 16))["subjects"][0]["trend"]["label"] == "kein Verlauf"
    # Die Route liefert dasselbe, für Kind und Eltern.
    from backend.routers import subjects as subjects_router
    client.app.include_router(subjects_router.router, prefix="/api")
    assert client.get("/api/accounts/1/subjects/stages").json()["subjects"][1]["label"] == "Latein"
    child(state)
    assert client.get("/api/accounts/1/subjects/stages").status_code == 200
    assert client.get("/api/accounts/2/subjects/stages").status_code == 403


def test_a_topic_without_material_says_so(env):
    """Ohne Originalseite darf der Einstieg keine erfinden. Am 17.09. behauptete
    er „Schulbuch S. 50“ und erfand den Inhalt, obwohl nichts vorlag (D96)."""
    from contextlib import closing
    from backend import db, lernstand
    with closing(db.webapp_conn()) as c, c:
        tid = c.execute(
            "INSERT INTO exam_topics(account_id,exam_key,subject,position,title,detail,stage,places_json,"
            "created_at,updated_at)"
            " VALUES(1,'k','SPANISCH',1,'Über Spanien sprechen','Länder beschreiben','neu','[]','now','now')").lastrowid
    ctx = lernstand.context_for(1, tid, None)
    assert ctx['material'] == [] and ctx['material_fehlt'] is True


def test_recognition_alone_is_not_sitzt():
    """Der Nutzer bindet „sitzt“ daran, dass die Aufgaben aus Buch und
    Arbeitsheft auch in den schwierigeren Niveaus richtig bearbeitet wurden
    (D97). Drei leichte Wiedergabeaufgaben reichen deshalb nicht."""
    leicht = [answer(1, "2026-09-16", kind="Erkenne", afb=1, form="auswahl"),
              answer(1, "2026-09-16", kind="Bilde", afb=1, form="auswahl"),
              answer(1, "2026-09-16", kind="Übersetze", afb=1, form="auswahl")]
    assert lernstand.replay(leicht)["stage"] == "wackelt"
    # Eine schwierigere richtig bearbeitete Aufgabe in der Serie genügt.
    gemischt = leicht[:2] + [answer(1, "2026-09-16", kind="Übersetze", afb=2, form="frei")]
    state = lernstand.replay(gemischt)
    assert state["stage"] == "sitzt" and "schwierigere" in state["reason"]


def test_the_chapter_is_the_basis_not_only_the_named_page(env):
    """Gelernt wird das Thema, nicht die Buchseite. Am 17.09. hing „Über Spanien
    und andere Länder sprechen" an Arbeitsheft S. 27 und Schulbuch S. 50, während
    S. 48 („Hier lernst du: über ein Land zu sprechen") ungenutzt im Bestand lag;
    der Mentor erfand daraufhin ein Quiz und schrieb es dem Material zu (D101)."""
    from backend.book_structure import Chapter, store_chapters
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) "
                  "VALUES(1,'spanisch','¡Apúntate! 2','now')")
        for page, title, text in [(48, 'Quiz', '¿Cuántas comunidades autónomas hay en España? a Hay 17.'),
                                  (49, 'Acércate', 'Hier lernst du: über ein Land zu sprechen.'),
                                  (50, 'Rally', 'Un rally por Madrid. El Parque del Retiro.'),
                                  (70, 'Unidad 4', 'Eine ganz andere Einheit.')]:
            c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,origin,source_book,"
                      "source_page,page_check,analysis_state,created_at,updated_at) "
                      "VALUES(1,'book_page','SPANISCH',?,?,'book_fetch','¡Apúntate! 2',?,'ok','ready','now','now')",
                      (title, text, page))
    store_chapters(1, '¡Apúntate! 2', [Chapter(number='3', title='De paseo por España', start_page=48, end_page=59),
                                       Chapter(number='4', title='Otra unidad', start_page=60, end_page=79)])
    places = [{'label': 'Schulbuch', 'pages': [50]}]
    material = lernstand.material_for(1, 'SPANISCH', places)
    stellen = [m['stelle'] for m in material]
    # Die genannte Seite zuerst, danach die Nachbarn desselben Kapitels, als solche benannt.
    assert stellen[0].startswith('Schulbuch S. 50') and 'gleiches Kapitel' not in stellen[0]
    assert any(s.startswith('Schulbuch S. 48') and 'gleiches Kapitel' in s for s in stellen)
    assert any('comunidades autónomas' in m['text'] for m in material), 'die tragende Seite fehlt dem Mentor'
    # Ein anderes Kapitel gehört nicht dazu.
    assert not any('S. 70' in s for s in stellen)
    # Dieselben Seiten kann das Kind aufschlagen.
    basis = lernstand.basis_of(1, 'SPANISCH', places)
    assert [(b['page'], b['chapter']) for b in basis] == [(50, False), (48, True), (49, True)]


def test_without_a_read_table_of_contents_nothing_is_added(env):
    """Ohne gelesenes Verzeichnis gibt es keine Kapitelgrenzen; dann bleibt es
    bei den genannten Stellen, statt irgendwelche Nachbarseiten anzuhängen."""
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,origin,source_book,"
                  "source_page,page_check,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','SPANISCH','S. 50','Un rally por Madrid.','book_fetch','¡Apúntate! 2',50,"
                  "'ok','ready','now','now')")
    assert lernstand.chapter_pages_of(1, 'SPANISCH', []) == []
    material = lernstand.material_for(1, 'SPANISCH', [{'label': 'Schulbuch', 'pages': [50]}])
    assert len(material) == 1 and 'gleiches Kapitel' not in material[0]['stelle']


def test_the_chapter_index_names_the_pages_the_collector_already_fetched(env):
    """Die Kapitelregel holt ohnehin alle Seiten eines angeschnittenen Kapitels
    und wertet sie aus. Der Mentor bekommt daraus ein Verzeichnis: eine Zeile je
    Seite mit ihrem Titel, dazu was noch fehlt. Ohne Inhalt — was auf einer Seite
    steht, weiß er erst, wenn sie im Material auftaucht (D104)."""
    from backend.book_structure import Chapter, store_chapters
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) "
                  "VALUES(1,'spanisch','¡Apúntate! 2','now')")
        for page, title in [(48, 'Quiz und Hörübung'), (50, 'Un rally por Madrid'), (52, 'El Prado')]:
            c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,origin,source_book,"
                      "source_page,page_check,analysis_state,created_at,updated_at) "
                      "VALUES(1,'book_page','SPANISCH',?,'Text der Seite.','book_fetch','¡Apúntate! 2',?,'ok','ready','now','now')",
                      (title, page))
    store_chapters(1, '¡Apúntate! 2', [Chapter(number='3', title='De paseo por España', start_page=48, end_page=52),
                                       Chapter(number='4', title='Otra unidad', start_page=53, end_page=60)])
    found = lernstand.chapter_context(1, 'SPANISCH', [{'label': 'Schulbuch', 'pages': [50]}])
    assert found['kapitel'] == '3 De paseo por España' and found['seiten'] == [48, 52]
    assert found['genannte_seiten'] == [50]
    assert [(p['seite'], p['titel']) for p in found['seiten_im_bestand']] == [
        (48, 'Quiz und Hörübung'), (50, 'Un rally por Madrid'), (52, 'El Prado')]
    # Was noch nicht geholt ist, steht als Lücke da und ist kein Verweisziel.
    assert found['seiten_fehlen'] == [49, 51]
    # Kein Seiteninhalt im Verzeichnis: nur Zahl und Titel.
    assert not any('Text der Seite' in str(v) for v in found['seiten_im_bestand'])
    # Ohne gelesenes Verzeichnis gibt es kein Kapitel und damit keinen Überblick.
    with closing(db.webapp_conn()) as c, c:
        c.execute("DELETE FROM book_chapters")
    assert lernstand.chapter_context(1, 'SPANISCH', [{'label': 'Schulbuch', 'pages': [50]}]) is None


def test_the_exam_scope_names_the_chapter_pages_it_has(env):
    """Dieselbe Übersicht wie in der Übungseinheit, auch für die Klausurvorbereitung:
    Das Kapitel nennt seine vorliegenden Seiten beim Namen, ohne ihren Volltext (D104)."""
    from backend.book_structure import Chapter, overview, store_chapters
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) "
                  "VALUES(1,'spanisch','¡Apúntate! 2','now')")
        c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,"
                  "part_kind,page,quote,synced_at,updated_at) "
                  "VALUES(1,'lesson',1,'2026-09-11','SPANISCH','','book',50,'S. 50','now','now')")
        for page, title in [(48, 'Quiz und Hörübung'), (50, 'Un rally por Madrid')]:
            c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,origin,source_book,"
                      "source_page,page_check,analysis_state,created_at,updated_at) "
                      "VALUES(1,'book_page','SPANISCH',?,'Text.','book_fetch','¡Apúntate! 2',?,'ok','ready','now','now')",
                      (title, page))
    store_chapters(1, '¡Apúntate! 2', [Chapter(number='3', title='De paseo por España', start_page=48, end_page=52)])
    found = overview(1, '¡Apúntate! 2', 'SPANISCH')
    assert len(found) == 1
    assert [(p['page'], p['title']) for p in found[0]['page_index']] == [(48, 'Quiz und Hörübung'), (50, 'Un rally por Madrid')]
    assert found[0]['pages_stored'] == 2 and found[0]['pages'] == 5
