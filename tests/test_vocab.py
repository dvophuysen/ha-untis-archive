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
    # Eigener Zweck: Das Lesen der Vokabellisten lässt sich unabhängig vom
    # übrigen Abschreiben auf eine andere Stufe legen (D103).
    assert calls[0][0] == "vocab"
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


def test_opening_the_trainer_reads_word_pages_by_itself_and_empty_pages_stay_quiet(setup):
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    grammar = seed_page(text="servus — der Sklave\n" * 3 + "Die a-Deklination …", page=13, title="Substantive der a-/o-Deklination")
    calls = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        calls.append(context["page"])
        return json.dumps(WORDS if context["page"] == 10 else {"words": []}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.get(V + "/LATEIN/units")
    assert r.status_code == 200 and r.json()["reading"] == 1
    # Der Hintergrundlauf ist nach der Antwort durch: Seite 10 gelesen, die Grammatikseite gar nicht angeboten.
    assert calls == [10]
    r = client.get(V + "/LATEIN/units").json()
    assert r["reading"] == 0 and r["units"][0]["words"] == 4 and r["units"][0]["unread"] == 0
    # Eine gelesene Seite ohne Lernwörter gilt nicht als ungelesen.
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE materials SET title='Wortschatz – Vokabeln sichern' WHERE id=?", (grammar,))
    r = client.get(V + "/LATEIN/units").json()
    assert r["reading"] == 1 and calls == [10, 13]
    r = client.get(V + "/LATEIN/units").json()
    assert r["reading"] == 0 and all(u["unread"] == 0 for u in r["units"])


def test_language_overview_lists_only_foreign_languages_with_their_state(setup):
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    import sqlite3
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("INSERT INTO lessons(account_id,date,subject_name,lstext) VALUES(1,'2026-09-11','LATEIN','Lektion 1')")
        c.execute("INSERT INTO lessons(account_id,date,subject_name,lstext) VALUES(1,'2026-09-11','Mathematik','Brüche')")
    mid = seed_page()
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO vocab_extractions(material_id,account_id,text_hash,words,updated_at) VALUES(?,1,'x',4,'now')", (mid,))
        for pos, w in enumerate(WORDS["words"][:4]):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) VALUES(1,'LATEIN',?,'Begleitband',10,'Lektion 1',?,?,?,?,'now')",
                      (mid, pos, w["foreign_word"], vocab.plain(w["foreign_word"]), json.dumps(w["meanings"])))
    r = client.get(V + "/languages")
    assert r.status_code == 200, r.text
    langs = r.json()["languages"]
    assert [l["subject"] for l in langs] == ["Latein"] and langs[0]["words"] == 4 and langs[0]["units"] == 1 and langs[0]["language"]["into"] is False


def test_parents_can_reset_a_language_and_children_cannot(setup):
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,foreign_word,plain,meanings_json,created_at) VALUES(1,'LATEIN',?,'Begleitband',10,'Lektion 1',0,'ecce','ecce',?,'now')", (mid, json.dumps(["Schau!"])))
        wid = c.execute("SELECT id FROM vocab_words").fetchone()[0]
        c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,created_at) VALUES(1,?,1,'from','Schau','correct','now')", (wid,))
    r = client.delete(V + "/LATEIN/attempts")
    assert r.status_code == 200 and r.json()["removed"] == 1 and r.json()["units"][0]["s1"]["neu"] == 1
    child(state)
    assert client.delete(V + "/LATEIN/attempts").status_code == 403


LIST_A = """171

Vocabulario

Unidad 3
Texto A ▸ p. 51

el país — das Land
limitar con — grenzen an

171 ciento setenta y uno"""
LIST_B = """172

Unidad 3
Texto B ▸ p. 53

el río — der Fluss

Unidad 4
Texto A ▸ p. 62

la tienda — der Laden

172 ciento setenta y dos"""


def test_a_unit_is_one_bundle_across_several_appendix_pages(setup):
    """Eine Unidad zieht sich über mehrere Anhangseiten; genau sie ist das
    Bündel, nicht die Anhangseite. Die Überschriften der Vokabelliste sagen,
    wohin ein Wort gehört, und gelten über den Seitenwechsel hinweg (D100)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    first = seed_page(subject="SPANISCH", text=LIST_A, page=171, label="", title="Vocabulario")
    second = seed_page(subject="SPANISCH", text=LIST_B, page=172, label="", title="Vocabulario")
    answers = {
        first: {"words": [
            {"unit": "Unidad 3", "section": "Texto A", "foreign_word": "el país", "meanings": ["das Land"]},
            {"unit": "Unidad 3", "section": "Texto A", "foreign_word": "limitar con", "meanings": ["grenzen an"]}]},
        second: {"words": [
            {"unit": "Unidad 3", "section": "Texto B", "foreign_word": "el río", "meanings": ["der Fluss"]},
            {"unit": "Unidad 4", "section": "Texto A", "foreign_word": "la tienda", "meanings": ["der Laden"]}]},
    }
    seen = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        seen.append(context["page"])
        return json.dumps(answers[first if context["page"] == 171 else second]), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.post(V + "/SPANISCH/extract", json={"material_ids": [first, second]})
    assert r.status_code == 200, r.text
    units = {u["unit"]: u for u in r.json()["units"] if u["words"]}
    # Zwei Anhangseiten, aber die Unidad ist das Bündel: drei Wörter in Unidad 3.
    assert units["Unidad 3"]["words"] == 3 and units["Unidad 4"]["words"] == 1
    assert [s["section"] for s in units["Unidad 3"]["sections"]] == ["Texto A", "Texto B"]
    assert [s["words"] for s in units["Unidad 3"]["sections"]] == [2, 1]
    # Standardbündel: die ganze Einheit über beide Seiten hinweg.
    whole = client.get(V + "/SPANISCH/cards?unit=Unidad%203&stage=1&direction=from").json()["cards"]
    assert [c["foreign_word"] for c in whole] == ["el país", "limitar con", "el río"]
    # Untergliederung: nur der genannte Abschnitt.
    part = client.get(V + "/SPANISCH/cards?unit=Unidad%203&section=Texto%20B&stage=1&direction=from").json()
    assert part["section"] == "Texto B" and [c["foreign_word"] for c in part["cards"]] == ["el río"]


def test_without_a_heading_the_page_keeps_its_own_label(setup):
    """Steht über den Wörtern keine Einheit, bleibt es beim Kapitel der Seite —
    erfunden wird keine."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()

    async def complete(account, purpose, instruction, context, *a, **kw):
        return json.dumps({"words": [{"foreign_word": "ecce", "meanings": ["Schau!"]}]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    unit = next(u for u in r.json()["units"] if u["words"])
    assert unit["unit"] == "Begleitband S. 10" and unit["sections"] == []


def test_the_word_reading_follows_the_copying_tier_until_it_gets_its_own(setup):
    """Das Lesen der Vokabellisten ist Formatarbeit auf sauberem Text mit einer
    harten Prüfung dahinter. Es bekommt eine eigene Stufenwahl, damit ein kleines
    Modell sie übernehmen kann, ohne das übrige Abschreiben mitzunehmen (D103).
    Ohne eigene Wahl gilt weiter die Stufe des Abschreibens."""
    client, state, patch = setup
    from backend.routers import mentor as m
    client.app.include_router(m.router, prefix="/api")
    with closing(db.webapp_conn()) as c, c:
        ai.init_config(c)
        c.execute("UPDATE mentor_ai_config SET sources_model='niedrig',vocab_model=NULL WHERE id=1")
    assert ai.tier_for(ai.VOCAB) == 'niedrig', 'ohne eigene Wahl wie das Abschreiben'
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_ai_config SET vocab_model='klein' WHERE id=1")
    assert ai.tier_for(ai.VOCAB) == 'klein' and ai.tier_for(ai.SOURCES) == 'niedrig'
    # Eltern setzen die Stufe über die Route; die Spracheingabe ist keine Wahl.
    r = client.put("/api/accounts/1/learning/mentor/budget-limits", json={'vocab_model': 'transkription'})
    assert r.status_code == 422
    assert client.put("/api/accounts/1/learning/mentor/budget-limits", json={'vocab_model': ''}).status_code == 200
    assert ai.tier_for(ai.VOCAB) == 'niedrig'


def test_the_word_reading_is_billed_to_the_source_budget_not_to_a_child(setup):
    """Das Lesen einer Vokabelseite gehört zum Quellenbestand, nicht zum
    Tagesbudget eines Kindes: Es gehört zu keiner Einheit."""
    with closing(db.webapp_conn()) as c, c:
        cfg = ai.init_config(c)
        over = ai.thresholds(c, {**cfg, 'sources_micro': 0, 'daily_micro': 10 ** 9},
                             1, ai.VOCAB, None, '2026-09-11', '2026-09', 1000)
    assert 'quellen' in over and 'tag' not in over


def test_parents_can_compare_tiers_on_one_page_without_storing_anything(setup):
    """Eichung vor dem Umlegen: dieselbe Seite mit zwei Stufen lesen, nichts
    ablegen, und sehen, was der kleineren fehlt (D103)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    by_tier = {
        'niedrig': {"words": [{"foreign_word": "ecce", "meanings": ["Schau!"]},
                              {"foreign_word": "esse", "meanings": ["sein"]}]},
        # Die kleine Stufe übersieht eines und erfindet eines, das nicht dasteht.
        'klein': {"words": [{"foreign_word": "ecce", "meanings": ["Schau!"]},
                            {"foreign_word": "amare", "meanings": ["lieben"]}]},
    }
    seen = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        seen.append((purpose, kw.get('tier')))
        return json.dumps(by_tier[kw.get('tier')]), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.post(V + "/LATEIN/compare", json={'material_id': mid, 'tiers': ['niedrig', 'klein']})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [p for p, _ in seen] == ['vocab', 'vocab']
    low, small = body['results']
    assert low['tier'] == 'niedrig' and low['kept'] == 2 and low['dropped'] == 0
    # „amare" steht nicht auf der Seite und fällt an der Prüfung heraus.
    assert small['kept'] == 1 and small['dropped'] == 1
    assert small['missing'] == ['esse'] and small['extra'] == []
    # Nichts abgelegt: Der Trainer kennt danach kein einziges Wort.
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_words").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM vocab_extractions").fetchone()[0] == 0
    # Kinder eichen nicht.
    child(state)
    assert client.post(V + "/LATEIN/compare", json={'material_id': mid, 'tiers': ['klein']}).status_code == 403
