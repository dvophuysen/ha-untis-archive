"""Sprechproben (D194): Prüfer im Chat, Bewertung am Ende mit Kriterien, Baustellen
und Nachprüfung, Referenzen aus dem Unterricht, Kalibrierung durch Eltern."""
import json
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, child  # noqa: F401
from test_mentor import setup, mock, B, TASK  # noqa: F401
from backend import db, exam_meta, oral_exam
from backend.routers import exams as exams_router, mentor as m

KEY = "uid:sprech-1"


def world():
    exam_meta.remember(1, KEY, "Sprechprüfung Englisch Jg.6 (Klausur)")
    exam_meta.set_note(1, KEY, "Sich vorstellen; Bild beschreiben")
    with closing(db.webapp_conn()) as c, c:
        own = c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,position,title,detail,origin,created_at,updated_at) "
                        "VALUES(1,'ENGLISCH',?,0,'Meine Familie','Personen beschreiben','manual','t','t')", (KEY,)).lastrowid
        c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,position,title,detail,origin,stale,created_at,updated_at) "
                  "VALUES(1,'ENGLISCH',?,1,'Simple past','Vergangenheit','assumed',1,'t','t')", (KEY,))
    return own


ASSESSMENT = {
    "scores": [{"criterion": k, "score": 3 if k != "grammatik" else 2, "evidence": "My sister have a dog.", "comment": ""}
               for k, _ in oral_exam.CRITERIA],
    "weak_spots": [{"label": "has statt have", "example": "My sister have a dog.", "better": "My sister has a dog.",
                    "next_check": "Nach Geschwistern und Haustieren fragen."}],
    "followups": [], "summary": "Du hast viel erzählt. Achte auf has bei he und she.", "level_note": "Etwa A1+.", "reliable": True}


def talk(client, s, texts):
    for i, t in enumerate(texts):
        r = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": f"talk_{i}_{s['version']}", "version": s["version"],
                                                              "text": t, "kind": "message", "spoken": True, "seconds": 6})
        assert r.status_code == 200, r.text
        s = r.json()
    return s


def test_simulation_from_start_to_assessment_and_the_next_one_checks_the_weak_spots(setup):
    client, state, patch = setup
    child(state)
    topic = world()
    contexts, instructions = [], []

    async def complete(account, purpose, instruction, context, *a, **kw):
        contexts.append(context)
        instructions.append(instruction)
        if "bewertest eine Sprechprobe" in instruction:
            return json.dumps(ASSESSMENT), {}, "x"
        return json.dumps({"message": "Nice! Who is in your family?", "choices": ["Tipp"], "action": "task",
                           "task": TASK, "assessment": None, "summary": "Familie vorgestellt."}), {}, "x"
    patch.setattr(m.ai, "complete", complete)
    r = client.post(B + "/sessions", json={"oral_exam_key": KEY, "topic_id": topic})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["mode"] == "oral" and s["oral"] == {"exam_key": KEY, "full": False} and s["untimed"]
    assert "Sprechprobe „Meine Familie“" in s["messages"][0]["text"] and "Englisch" in s["messages"][0]["text"]
    assert client.post(B + "/sessions", json={"oral_exam_key": KEY, "topic_id": topic}).json()["id"] == s["id"], "laufende Probe geht wieder auf"
    s = talk(client, s, ["I have a sister.", "My sister have a dog.", "We play football on Sunday."])
    ctx, instruction = contexts[-1], instructions[-1]
    assert "SPRECHPROBE" in instruction and ctx["oral"]["niveau"].startswith("GER A1+ bis A2")
    assert ctx["oral"]["hinweise_eltern"] == "Sich vorstellen; Bild beschreiben"
    assert ctx["oral"]["unterricht"]["themen_im_unterricht"] == ["Simple past · Vergangenheit"], "zurückgetretener Stoff bleibt Maßstab"
    assert "Sprechprüfung" in ctx["topic"]["pruefungsform"]
    last = s["messages"][-1]
    assert last["payload"]["task"] is None and last["payload"]["choices"] == [], "keine Aufgaben, keine Knöpfe in der Probe"
    assert s["messages"][-2]["payload"]["seconds"] == 6 and s["messages"][-2]["payload"]["spoken"]
    r = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "finish_1", "version": s["version"], "text": "Beenden und auswerten", "kind": "finish"})
    assert r.status_code == 200, r.text
    s = r.json()
    result = s["messages"][-1]["payload"]["oral_result"]
    assert s["status"] == "completed" and result["reliable"] and [x["criterion"] for x in result["scores"]] == [k for k, _ in oral_exam.CRITERIA]
    assert result["weak_spots"][0]["better"] == "My sister has a dog." and result["lowest"] == 2
    assessed = contexts[-1]
    assert assessed["messwerte"]["antworten"] == 3 and assessed["messwerte"]["woerter_je_minute"] == round(14 / 18 * 60)
    assert [t.get("kind") for t in assessed["gespraech"] if "kind" in t] == ["I have a sister.", "My sister have a dog.", "We play football on Sunday."]
    assert oral_exam.done_on(1, KEY, topic, "2026-01-01", "2030-01-01") and not oral_exam.topic_ready(1, KEY, topic)
    # Die nächste Probe bekommt die Baustelle mit.
    r2 = client.post(B + "/sessions", json={"oral_exam_key": KEY})
    assert r2.status_code == 200, r2.text
    s2 = r2.json()
    assert s2["id"] != s["id"] and s2["oral"]["full"]
    talk(client, s2, ["Hello."])
    assert contexts[-1]["oral"]["baustellen_letztes_mal"][0]["label"] == "has statt have"


def test_too_short_is_not_assessed_by_the_model(setup):
    client, state, patch = setup
    child(state)
    topic = world()
    calls = []
    mock(patch, [{"message": "Hello! Tell me about your family.", "choices": [], "action": "clarify", "task": None, "assessment": None, "summary": ""}], calls)
    s = client.post(B + "/sessions", json={"oral_exam_key": KEY, "topic_id": topic}).json()
    s = talk(client, s, ["Hi."])
    n = len(calls)
    s = client.post(B + f"/sessions/{s['id']}/turn", json={"request_key": "finish_2", "version": s["version"], "kind": "finish"}).json()
    assert len(calls) == n and not s["messages"][-1]["payload"]["oral_result"]["reliable"]
    assert not oral_exam.topic_ready(1, KEY, topic)


def test_no_simulation_for_a_written_exam(setup):
    client, state, patch = setup
    exam_meta.remember(1, "uid:mathe", "Mathematik Klassenarbeit")
    assert client.post(B + "/sessions", json={"oral_exam_key": "uid:mathe"}).status_code == 422


def test_references_verdict_and_readiness(setup):
    client, state, patch = setup
    client.app.include_router(exams_router.router, prefix="/api")
    topic = world()
    refs = oral_exam.references(1, KEY, "ENGLISCH")
    assert [r["label"] for r in refs if r["kind"] == "topic"] == ["Simple past · Vergangenheit"] and all(r["checked"] for r in refs)
    r = client.post("/api/accounts/1/exams/note", json={"exam_key": KEY, "note": "Sich vorstellen", "excluded_refs": [refs[0]["key"]]})
    assert r.status_code == 200 and not oral_exam.references(1, KEY, "ENGLISCH")[0]["checked"]
    assert oral_exam.reference_context(1, KEY, "ENGLISCH")["themen_im_unterricht"] == []
    good = [{"criterion": k, "score": 3, "evidence": "x"} for k, _ in oral_exam.CRITERIA]
    with closing(db.webapp_conn()) as c, c:
        for full in (0, 1):
            c.execute("INSERT INTO oral_sims(account_id,exam_key,topic_id,full,session_id,created_at,scores_json,reliable) VALUES(1,?,?,?,1,'2026-09-28T15:00:00',?,1)",
                      (KEY, None if full else topic, full, json.dumps(good)))
    assert oral_exam.topic_ready(1, KEY, topic), "Themenprobe und Gesamtprobe decken das Thema zweimal ab"
    assert oral_exam.full_ready(1, KEY)
    sim = oral_exam.sims(1, KEY)[0]
    assert client.post(f"/api/accounts/1/exams/oral-sims/{sim['id']}/verdict", json={"verdict": "streng"}).status_code == 200
    assert oral_exam.calibration(1, KEY)[0].startswith("Eltern: diese Bewertung war zu streng")
    child(state)
    assert client.post(f"/api/accounts/1/exams/oral-sims/{sim['id']}/verdict", json={"verdict": "mild"}).status_code in (403, 404)


def test_speech_is_transcribed_verbatim_in_a_simulation():
    s = {"id": 1, "subject": "ENGLISCH", "goal": "Sprechprobe", "current_task": None, "source_json": json.dumps({"mode": "oral"})}
    assert "Fehler und Zögern bleiben stehen" in m.speech_prompt(None, s)


def test_level_by_grade():
    assert oral_exam.level_for("6").startswith("GER A1+") and oral_exam.level_for(8).startswith("GER A2") and oral_exam.level_for("10").startswith("GER B1")


def test_teacher_handout_is_the_exam_structure_not_speaking_topics(setup):
    """D195: Bei einer Sprechprüfung beschreibt der Zettel der Lehrkraft den Ablauf
    (Interview, Monologue, Dialogue); Sprechproben je Thema gibt es nur für
    eingetragene Sprechthemen."""
    topic = world()
    with closing(db.webapp_conn()) as c, c:
        for i, (title, detail) in enumerate([("Interview", "Fragen zu einem bekannten Thema."), ("Monologue", "Bildbeschreibung.")]):
            c.execute("INSERT INTO exam_topics(account_id,subject,exam_key,position,title,detail,origin,created_at,updated_at) "
                      "VALUES(1,'ENGLISCH',?,?,?,?,'notice','t','t')", (KEY, 5 + i, title, detail))
    assert [t["id"] for t in oral_exam.spoken_topics(1, KEY)] == [topic]
    ctx = oral_exam.context(1, {"exam_key": KEY, "full": True}, "ENGLISCH", 6)
    assert [p["punkt"] for p in ctx["pruefungsaufbau"]] == ["Interview", "Monologue"] and len(ctx["alle_sprechthemen"]) == 1
    assert all(r["kind"] != "topic" or "Interview" not in r["label"] for r in oral_exam.references(1, KEY, "ENGLISCH"))
    assert "Teil für Teil" in oral_exam.ORAL_RULE
