"""Vokabeltrainer: Wörter aus Originalseiten, Bewertung, Stufen je Wort, Brücke zur Themenliste."""
import json
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path  # noqa: F401
from test_mentor import setup  # noqa: F401
from backend import db, vocab, lernstand, ai_gateway as ai
from backend.routers import vocab as vocab_router

V = "/api/accounts/1/learning/vocab"
PAGE = """1
WORTSCHATZ

Lernwörter

A

ecce — Schau! Schaut!
esse — sein, sich befinden
servus  m — der Sklave, der Diener
cōgitāre — denken, nachdenken, beabsichtigen
Etiam Syrus servus est.
Auch Syrus ist ein Sklave.

10"""
WORDS = {"words": [
    {"foreign_word": "ecce", "meanings": ["Schau!", "Schaut!"], "grammar": "", "forms": {}, "example": ""},
    {"foreign_word": "esse", "meanings": ["sein", "sich befinden"], "grammar": "", "forms": {}, "example": ""},
    {"foreign_word": "servus", "meanings": ["der Sklave", "der Diener"], "grammar": "m", "forms": {}, "example": "Etiam Syrus servus est."},
    {"foreign_word": "cōgitāre", "meanings": ["denken", "nachdenken", "beabsichtigen"], "grammar": "", "forms": {}, "example": ""},
    {"foreign_word": "gaudēre", "meanings": ["sich freuen"], "grammar": "", "forms": {}, "example": ""},
]}


def test_meaning_judgement_is_lenient_about_form_but_not_about_sense():
    assert vocab.judge_meaning("Sklave", ["der Sklave", "der Diener"]) == ("correct", "der Sklave")
    assert vocab.judge_meaning("der diener", ["der Sklave", "der Diener"]) == ("correct", "der Diener")
    assert vocab.judge_meaning("denken, nachdenken", ["denken", "nachdenken", "beabsichtigen"])[0] == "correct"
    assert vocab.judge_meaning("kaputt machen", ["(zer)brechen; kaputt machen"])[0] == "correct"
    assert vocab.judge_meaning("zerbrechen", ["(zer)brechen; kaputt machen"])[0] == "correct"
    assert vocab.judge_meaning("Pferd", ["der Sklave"]) == ("incorrect", None)
    # Ein Hörfehler nah an der Bedeutung: nachfragen, nicht werten.
    assert vocab.judge_meaning("Sklafe", ["der Sklave"])[0] in ("correct", "unclear")
    assert vocab.judge_meaning("bedenken", ["denken"])[0] == "unclear"
    assert vocab.judge_meaning("", ["denken"]) == ("incorrect", None)


def test_spelling_counts_every_letter_and_speech_counts_the_sound():
    assert vocab.judge_foreign("to apply for", "to apply for", spoken=False) == ("correct", "")
    assert vocab.judge_foreign("apply for", "to apply for", spoken=False) == ("correct", "")
    assert vocab.judge_foreign("to aply for", "to apply for", spoken=False)[0] == "partial"
    assert vocab.judge_foreign("to appel", "to apply for", spoken=False)[0] == "incorrect"
    assert vocab.judge_foreign("Apply.", "to apply", spoken=True) == ("correct", "")
    assert vocab.judge_foreign("aply", "to apply", spoken=True) == ("correct", "")
    assert vocab.judge_foreign("supply", "to apply", spoken=True)[0] == "unclear"
    assert vocab.judge_foreign("cogitare", "cōgitāre", spoken=False) == ("correct", "")


def att(day, result="correct", seconds=4):
    return {"result": result, "seconds": seconds, "created_at": f"{day}T16:00:00+02:00"}


def test_word_stage_two_clean_sits_three_days_later_settles_and_errors_wobble():
    assert vocab.replay([])["stage"] == "neu"
    assert vocab.replay([att("2026-09-16")])["stage"] == "wackelt"
    state = vocab.replay([att("2026-09-16"), att("2026-09-16")])
    assert state["stage"] == "sitzt" and state["due"] == "2026-09-19"
    assert vocab.replay([att("2026-09-16"), att("2026-09-16"), att("2026-09-19")])["stage"] == "gefestigt"
    assert vocab.replay([att("2026-09-16"), att("2026-09-16", seconds=30)])["stage"] == "wackelt"
    assert vocab.replay([att("2026-09-16"), att("2026-09-16"), att("2026-09-19", "incorrect")])["stage"] == "wackelt"
    # Eine Rückfrage zählt nicht, weder gut noch schlecht.
    assert vocab.replay([att("2026-09-16"), att("2026-09-16", "unclear"), att("2026-09-16")])["stage"] == "sitzt"


def seed_page(account=1, subject="LATEIN", text=PAGE, page=10, label="Begleitband", title="Lernwörter der Lektion 1"):
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,summary,content_text,source_label,source_page,analysis_state,created_at,updated_at) "
                  "VALUES(?,'book_page',?,?,'',?,?,?,'ready','2026-09-10T10:00:00','2026-09-10T10:00:00')",
                  (account, subject, title, text, label, page))
        return c.execute("SELECT max(id) FROM materials").fetchone()[0]


def test_words_come_from_the_page_once_and_must_stand_in_its_text(setup):
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    calls = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        calls.append((purpose, context))
        return json.dumps(WORDS), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.get(V + "/LATEIN/units")
    assert r.status_code == 200, r.text
    assert r.json()["language"]["name"] == "Latein" and r.json()["language"]["into"] is False
    unit = r.json()["units"][0]
    assert unit["unit"] == "Begleitband S. 10" and unit["unread"] == 1 and unit["words"] == 0
    r = client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert r.status_code == 200, r.text
    # gaudēre steht nicht auf der Seite: verworfen. Vier Wörter bleiben.
    assert r.json()["words"] == {mid: 4} or r.json()["words"] == {str(mid): 4}
    assert calls[0][0] == "sources"
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert len(calls) == 1
    cards = client.get(V + "/LATEIN/cards?unit=Begleitband%20S.%2010&stage=1&direction=from").json()["cards"]
    assert [c["foreign_word"] for c in cards] == ["ecce", "esse", "servus", "cōgitāre"]
    assert cards[2]["meanings"] == ["der Sklave", "der Diener"] and cards[2]["state"]["s1"]["stage"] == "neu"
    # Latein wird nicht in die Fremdsprache geprüft.
    assert client.get(V + "/LATEIN/cards?unit=x&stage=1&direction=into").status_code == 422
    assert client.get(V + "/LATEIN/cards?unit=x&stage=2&direction=from").status_code == 422


def test_attempts_move_the_word_and_wobblers_come_first(setup):
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    patch.setattr(vocab, "now_iso", lambda: "2026-09-11T16:00:00+02:00")
    patch.setattr(vocab, "today_local", lambda: date(2026, 9, 11))
    mid = seed_page()
    with closing(db.webapp_conn()) as c, c:
        for pos, w in enumerate(WORDS["words"][:3]):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) VALUES(1,'LATEIN',?, 'Begleitband',10,'Lektion 1',?,?,?,?,'now')",
                      (mid, pos, w["foreign_word"], vocab.plain(w["foreign_word"]), json.dumps(w["meanings"])))
        ids = [r[0] for r in c.execute("SELECT id FROM vocab_words ORDER BY position")]
    r = client.post(V + "/attempts", json={"word_id": ids[2], "stage": 1, "direction": "from", "answer": "Sklave", "spoken": True, "seconds": 3})
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "correct" and r.json()["feedback"].startswith("Richtig. Im Buch: servus") and r.json()["word"]["state"]["s1"]["stage"] == "wackelt"
    r = client.post(V + "/attempts", json={"word_id": ids[2], "stage": 1, "direction": "from", "answer": "Diener", "seconds": 5})
    assert r.json()["word"]["state"]["s1"]["stage"] == "sitzt"
    # Ein Buchstabe daneben ist bei einer Bedeutung kein Fehler.
    r = client.post(V + "/attempts", json={"word_id": ids[1], "stage": 1, "direction": "from", "answer": "sain", "seconds": 2})
    assert r.json()["result"] == "correct"
    # Nah dran, aber nicht sicher: Rückfrage, nichts gebucht; die Bestätigung zählt als richtig mit Zögern.
    r = client.post(V + "/attempts", json={"word_id": ids[0], "stage": 1, "direction": "from", "answer": "Schade", "seconds": 2})
    assert r.json()["result"] == "unclear" and "Meintest du" in r.json()["feedback"]
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_attempts WHERE word_id=?", (ids[0],)).fetchone()[0] == 0
    r = client.post(V + "/attempts", json={"word_id": ids[0], "stage": 1, "direction": "from", "answer": "Schade", "seconds": 2, "confirm": True})
    assert r.json()["result"] == "correct" and "Zögern" in r.json()["feedback"]
    # Falsch: wackelt, und die Karte rückt nach vorn.
    r = client.post(V + "/attempts", json={"word_id": ids[2], "stage": 1, "direction": "from", "answer": "Pferd", "seconds": 2})
    assert r.json()["result"] == "incorrect" and "Im Buch: servus · der Sklave, der Diener" in r.json()["feedback"]
    cards = client.get(V + "/LATEIN/cards?unit=Lektion%201&stage=1&direction=from").json()["cards"]
    assert cards[0]["foreign_word"] == "servus" and cards[0]["state"]["s1"]["stage"] == "wackelt"
    units = client.get(V + "/LATEIN/units").json()["units"]
    assert units[0]["s1"] == {"neu": 0, "wackelt": 3, "sitzt": 0, "gefestigt": 0}
    # Aufgeben ist eine falsche Antwort mit Erklärung.
    r = client.post(V + "/attempts", json={"word_id": ids[0], "stage": 1, "direction": "from", "gave_up": True})
    assert r.json()["result"] == "incorrect" and r.json()["feedback"].startswith("Weiß ich nicht.")


def test_english_spelling_stage_needs_the_meaning_first(setup):
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page(subject="ENGLISCH", text="Irregular verbs\nto apply for | applied | applied | sich bewerben\n", page=206, label="Schulbuch", title="Vocabulary")
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) VALUES(1,'ENGLISCH',?,'Schulbuch',206,'Unit 1',0,'to apply for','apply for',?,'now')", (mid, json.dumps(["sich bewerben"])))
        wid = c.execute("SELECT id FROM vocab_words").fetchone()[0]
    assert client.get(V + "/ENGLISCH/cards?unit=Unit%201&stage=2&direction=into").json()["cards"] == []
    for _ in range(2):
        client.post(V + "/attempts", json={"word_id": wid, "stage": 1, "direction": "into", "answer": "to apply", "spoken": True, "seconds": 3})
    cards = client.get(V + "/ENGLISCH/cards?unit=Unit%201&stage=2&direction=into").json()["cards"]
    assert [c["foreign_word"] for c in cards] == ["to apply for"]
    r = client.post(V + "/attempts", json={"word_id": wid, "stage": 2, "direction": "into", "answer": "to aply for", "seconds": 9})
    assert r.json()["result"] == "partial" and "Fast. Ein Buchstabe" in r.json()["feedback"] and "to apply for" in r.json()["feedback"]
    assert r.json()["word"]["state"]["s2"]["stage"] == "wackelt" and r.json()["word"]["state"]["s1"]["stage"] == "sitzt"
    assert client.post(V + "/attempts", json={"word_id": wid, "stage": 2, "direction": "from", "answer": "x"}).status_code == 422


def test_vocab_topic_of_the_list_takes_its_stage_from_the_words(setup):
    client, state, patch = setup
    mid = seed_page()
    tid = lernstand.add_manual(1, "cal:latein", "LATEIN", "Voc. 1. Lektion")["id"]
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE exam_topics SET places_json=? WHERE id=?", (json.dumps([{"label": "", "pages": [10, 11]}]), tid))
        for pos, w in enumerate(WORDS["words"][:2]):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) VALUES(1,'LATEIN',?,'Begleitband',10,'Lektion 1',?,?,?,?,'now')",
                      (mid, pos, w["foreign_word"], vocab.plain(w["foreign_word"]), json.dumps(w["meanings"])))
        ids = [r[0] for r in c.execute("SELECT id FROM vocab_words ORDER BY position")]
        for wid in ids[:1]:
            for _ in range(2):
                c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,seconds,created_at) VALUES(1,?,1,'from','x','correct',3,'2026-09-11T16:00:00+02:00')", (wid,))
    topics = lernstand.topics_for(1, "cal:latein", "LATEIN")
    t = topics[0]
    assert t["vocab"] is True and t["vocab_unit"] == "Lektion 1" and t["words"] == 2
    assert t["stage"] == "angefangen" and t["reason"] == "1 von 2 Wörtern sitzen"
    with closing(db.webapp_conn()) as c, c:
        for _ in range(2):
            c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,seconds,created_at) VALUES(1,?,1,'from','x','correct',3,'2026-09-11T16:00:00+02:00')", (ids[1],))
    assert lernstand.topics_for(1, "cal:latein", "LATEIN")[0]["stage"] == "sitzt"
    assert not lernstand.is_vocab_topic({"title": "Substantive: a/o-Deklination"}) and lernstand.is_vocab_topic({"title": "Voc. 1. Lektion"})
