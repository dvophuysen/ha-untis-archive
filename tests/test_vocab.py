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


def ai_answers(patch, woerter=None, koepfe=None, gesehen=None):
    """Beide Fragen einer Vokabelseite beantworten: Wörter und Überschriften.

    Jede Antwort ist entweder fest oder je Seitenzahl gestaffelt. Erkannt wird
    die Frage am Zusammenhang: Die Wörterfrage bekommt das Fach mit."""
    def pick(table, page, leer):
        if table is None:
            return leer
        if isinstance(table, dict) and not (set(table) & {"words", "ueberschriften", "beginnt_mit_ueberschrift"}):
            return table.get(page, leer)
        return table

    async def complete(account, purpose, instruction, context, *a, **kw):
        if "subject" in context:
            if gesehen is not None:
                gesehen.append(context["page"])
            return json.dumps(pick(woerter, context["page"], {"words": []})), {}, "fake"
        return json.dumps(pick(koepfe, context["seite"], {"ueberschriften": []})), {}, "fake"
    patch.setattr(ai, "complete", complete)
    return complete


def kopf(titel, erstes_wort="", wo="im_text", groesser=False, farbig=False, gerahmt=False):
    return {"titel": titel, "erstes_wort": erstes_wort, "wo": wo,
            "groesser": groesser, "farbig": farbig, "gerahmt": gerahmt}


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
        # Die Überschriftenfrage ist ein eigener, kleiner Aufruf (D139); gezählt
        # wird hier nur das Lesen der Wörter.
        if "subject" not in context:
            return json.dumps({"ueberschriften": []}), {}, "fake"
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
        if 'woerter' in context:
            return json.dumps({"headings": []}), {}, "fake"
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
    Bündel, nicht die Anhangseite. Die Überschriften sagen, wohin ein Wort
    gehört, und gelten über den Seitenwechsel hinweg (D100, D139)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    first = seed_page(subject="SPANISCH", text=LIST_A, page=171, label="", title="Vocabulario")
    second = seed_page(subject="SPANISCH", text=LIST_B, page=172, label="", title="Vocabulario")
    woerter = {
        171: {"words": [{"foreign_word": "el país", "meanings": ["das Land"]},
                        {"foreign_word": "limitar con", "meanings": ["grenzen an"]}]},
        172: {"words": [{"foreign_word": "el río", "meanings": ["der Fluss"]},
                        {"foreign_word": "la tienda", "meanings": ["der Laden"]}]},
    }
    koepfe = {
        171: {"ueberschriften": [kopf("Vocabulario", wo="seitenkopf"),
                                 kopf("Unidad 3", "el país", groesser=True),
                                 kopf("Texto A ▸ p. 51", "el país")],
              "beginnt_mit_ueberschrift": True},
        172: {"ueberschriften": [kopf("Texto B ▸ p. 53", "el río"),
                                 kopf("Unidad 4", "la tienda", groesser=True),
                                 kopf("Texto A ▸ p. 62", "la tienda")],
              "beginnt_mit_ueberschrift": True},
    }
    ai_answers(patch, woerter, koepfe)
    r = client.post(V + "/SPANISCH/extract", json={"material_ids": [first, second]})
    assert r.status_code == 200, r.text
    units = {u["unit"]: u for u in r.json()["units"] if u["words"]}
    # Zwei Anhangseiten, aber die Unidad ist das Bündel: drei Wörter in Unidad 3.
    # „el río" steht unter „Texto B" auf der Folgeseite und gehört noch dazu,
    # weil dort keine neue Einheit beginnt.
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
        if "subject" not in context:
            return json.dumps({"ueberschriften": [kopf("Lektion 1", "ecce", groesser=True)]}), {}, "fake"
        return json.dumps(by_tier[kw.get('tier')]), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.post(V + "/LATEIN/compare", json={'material_id': mid, 'tiers': ['niedrig', 'klein']})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [p for p, _ in seen] == ['vocab'] * 4, 'je Stufe die Wörter und die Überschriften'
    low, small = body['results']
    assert low['tier'] == 'niedrig' and low['kept'] == 2 and low['dropped'] == 0
    # Mitgeeicht wird die Gliederung, denn an ihr hängt die Bündelung.
    assert [h['titel'] for h in low['headings']] == ['Lektion 1']
    # „amare" steht nicht auf der Seite und fällt an der Prüfung heraus.
    assert small['kept'] == 1 and small['dropped'] == 1
    assert small['missing'] == ['esse'] and small['extra'] == []
    # Nichts abgelegt: Der Trainer kennt danach kein einziges Wort.
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM vocab_words").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM vocab_extractions").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM vocab_headings").fetchone()[0] == 0
    # Kinder eichen nicht.
    child(state)
    assert client.post(V + "/LATEIN/compare", json={'material_id': mid, 'tiers': ['klein']}).status_code == 403


def test_the_fields_are_tidied_so_the_bundling_does_not_depend_on_the_model():
    """Die Eichung zeigte: Beide Stufen finden dieselben Wörter, halten sich aber
    unterschiedlich streng an die Feldkonventionen. Das eine Modell schrieb
    „las gafas de sol pl." als Stichwort — in Stufe 2 nur zu tippen, wenn das
    Kind auch „pl." schreibt (D107)."""
    a, b = vocab.tidy([
        vocab.WordIn(foreign_word='las gafas de sol pl.', meanings=['die Sonnenbrille']),
        vocab.WordIn(foreign_word='el/la siguiente (sust.)', meanings=['der folgende'], grammar='m/f')])
    assert (a.foreign_word, a.grammar) == ('las gafas de sol', 'pl.')
    # Eine Marke in Klammern ist schon getrennt; eine vorhandene Angabe bleibt.
    assert (b.foreign_word, b.grammar) == ('el/la siguiente (sust.)', 'm/f')
    # Und der Verweis gehört nicht in den Namen der Einheit: Sonst zerfiele ein
    # Kapitel in so viele Bündel, wie es Verweise hat (D100).
    assert vocab.clean_unit('Unidad 3 ¡Acércate!  ▶ p. 48') == vocab.clean_unit('Unidad 3 ¡Acércate!')


def test_a_changed_reading_instruction_reads_the_page_again(setup):
    """Eine Seite wird je Textstand einmal gelesen. Als die Anweisung um die
    Gliederung erweitert wurde, trugen die schon gelesenen Anhangseiten weiter
    ihre alten Seitenbündel — S. 171 und S. 172 standen als zwei Bündel da statt
    als eine Unidad, und nichts las sie je wieder (D108)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    calls = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        if "subject" not in context:
            return json.dumps({"ueberschriften": []}), {}, "fake"
        calls.append(1)
        return json.dumps({"words": [{"foreign_word": "ecce", "meanings": ["Schau!"]}]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert len(calls) == 1, "derselbe Text, dieselbe Anweisung: kein zweiter Aufruf"
    patch.setattr(vocab, "EXTRACT_VERSION", vocab.EXTRACT_VERSION + 1)
    # Die Seite gilt jetzt als veraltet, und der Hintergrundlauf holt sie sich.
    # Ohne das käme eine Änderung der Anweisung bei schon gelesenen Seiten nie
    # an: Er sah nur Seiten an, die noch gar nicht gelesen waren (D108).
    assert [p["stale"] for p in vocab.pages(1, "LATEIN")] == [True]
    assert vocab.unread_pages(1, "LATEIN") == [mid]
    assert client.get(V + "/LATEIN/units").json()["reading"] == 1
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert len(calls) == 2, "neue Anweisung: die Seite wird noch einmal gelesen"
    assert vocab.unread_pages(1, "LATEIN") == [], "danach ist sie wieder aktuell"
    # Dasselbe für die Überschriftenfrage: eigener Zähler, eigener Stand.
    patch.setattr(vocab, "HEADS_VERSION", vocab.HEADS_VERSION + 1)
    assert vocab.unread_pages(1, "LATEIN") == [mid]
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert len(calls) == 2, "die Wörter bleiben davon unberührt"
    assert vocab.unread_pages(1, "LATEIN") == []


def test_pages_from_lessons_are_no_longer_offered_as_bundles(setup):
    """Geübt werden Einheiten, nicht einzelne Seiten aus dem Unterricht. Solange
    es aber noch keine Einheit mit Wörtern gibt, bleiben die Seiten stehen,
    damit der Trainer nicht leer dasteht (D100)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    sheet = seed_page(subject="SPANISCH", text="una palabra — ein Wort", page=26, label="Arbeitsheft", title="Wortschatz")
    liste = seed_page(subject="SPANISCH", text="el país — das Land", page=171, label="Schulbuch", title="Vocabulario")
    ai_answers(patch,
               {26: {"words": [{"foreign_word": "una palabra", "meanings": ["ein Wort"]}]},
                171: {"words": [{"foreign_word": "el país", "meanings": ["das Land"]}]}},
               # Die Heftseite trägt keine Überschrift, die Wortliste schon.
               {171: {"ueberschriften": [kopf("Unidad 3", "el país", groesser=True)],
                      "beginnt_mit_ueberschrift": True}})
    # Nur die Heftseite gelesen: Sie bleibt stehen, sonst gäbe es gar nichts.
    client.post(V + "/SPANISCH/extract", json={"material_ids": [sheet]})
    assert [u["unit"] for u in vocab.units(1, "SPANISCH") if u["words"]] == ["Arbeitsheft S. 26"]
    # Sobald eine echte Einheit Wörter hat, tritt die Seite zurück.
    client.post(V + "/SPANISCH/extract", json={"material_ids": [liste]})
    offered = [u["unit"] for u in vocab.units(1, "SPANISCH")]
    assert "Unidad 3" in offered and "Arbeitsheft S. 26" not in offered


def test_one_unit_is_one_bundle_even_under_two_names(setup):
    """Die Vokabelliste schreibt „Unidad 3", das Inhaltsverzeichnis „Unidad 3
    De paseo por España". Dasselbe Kapitel stand dadurch zweimal im Trainer,
    einmal mit Wörtern und einmal ohne. Jetzt ist es ein Bündel, unter dem
    ausführlicheren Namen; ein Bündel ganz ohne Wörter entfällt (D100)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    liste = seed_page(subject="SPANISCH", text="el país — das Land\nel río — der Fluss", page=171,
                      label="Schulbuch", title="Vocabulario")
    heft = seed_page(subject="SPANISCH", text="la tienda — der Laden", page=18,
                     label="Grammatikheft", title="Wortschatz")
    ai_answers(patch,
               {171: {"words": [{"foreign_word": "el país", "meanings": ["das Land"]},
                                {"foreign_word": "el río", "meanings": ["der Fluss"]}]},
                18: {"words": [{"foreign_word": "la tienda", "meanings": ["der Laden"]}]}},
               {171: {"ueberschriften": [kopf("Unidad 3", "el país", groesser=True)],
                      "beginnt_mit_ueberschrift": True},
                18: {"ueberschriften": [kopf("Unidad 3 De paseo por España", "la tienda", groesser=True)],
                     "beginnt_mit_ueberschrift": True}})
    client.post(V + "/SPANISCH/extract", json={"material_ids": [liste, heft]})
    found = vocab.units(1, "SPANISCH")
    assert [u["unit"] for u in found] == ["Unidad 3 De paseo por España"], found
    assert found[0]["words"] == 3, "die Wörter beider Schreibweisen zusammen"
    # Und die Karten gehören alle dazu, egal unter welchem der beiden Namen
    # das Bündel angetippt wird.
    for name in ("Unidad 3", "Unidad 3 De paseo por España"):
        assert len(vocab.cards(1, "SPANISCH", name, 1, "from")) == 3, name
    # Auch über einen dritten Namen hinweg: Das Grammatikheft nummeriert nur
    # „3", das Schulbuch „Unidad 3"; beide meinen dasselbe Kapitel.
    assert vocab.group_units(["Unidad 3", "3 De paseo por España", "Unidad 3 De paseo por España", "Unidad 4"]) \
        == {"Unidad 3": "de paseo por espana", "3 De paseo por España": "de paseo por espana",
            "Unidad 3 De paseo por España": "de paseo por espana", "Unidad 4": "unidad 4"}
    assert "el país" in vocab.prompt_for(1, "SPANISCH", "Unidad 3 De paseo por España", "into")


def test_a_bare_number_belongs_to_the_unit_of_the_same_name():
    """Green Line schreibt in seiner Wortliste nur „1", „2", „3" und stellt
    daneben „Unit 1 On the move". Dieselbe Unit, also ein Bündel. „TS 1" und
    „AC 2" sind eigene Reihen des Buchs und bleiben getrennt (D110)."""
    from collections import defaultdict
    found = defaultdict(list)
    for name, key in vocab.group_units(
            ['1', '2', '3', 'Unit 1 On the move', 'Unit 2', 'Unit 3', 'TS 1', 'TS 2', 'AC 2']).items():
        found[key].append(name)
    groups = sorted(sorted(v) for v in found.values())
    assert groups == [['1', 'Unit 1 On the move'], ['2', 'Unit 2'], ['3', 'Unit 3'],
                      ['AC 2'], ['TS 1'], ['TS 2']], groups
    # Ohne eindeutige Reihe bleibt die bloße Nummer für sich: Sonst riete die App.
    zwei = vocab.group_units(['1', 'Unit 1 On the move', 'Lektion 1 Anfang'])
    assert len({zwei['1'], zwei['Unit 1 On the move']}) == 2


def test_units_are_named_and_ordered_like_the_book(setup):
    """Die Wortliste schreibt mal „Unidad 3", mal nichts weiter; im Trainer hieß
    eine Einheit dann mit Titel und die nächste ohne. Und die Reihenfolge
    verrutschte, weil nach der ersten Seite eines Bündels sortiert wurde — nach
    dem Zusammenführen ist das mal die Anhangseite, mal die Kapitelseite (D113)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    from backend.book_structure import Chapter, store_chapters
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) "
                  "VALUES(1,'spanisch','¡Apúntate! 2','now')")
    store_chapters(1, '¡Apúntate! 2', [
        Chapter(number='Unidad 1', title='Hola', start_page=10, end_page=25),
        Chapter(number='Unidad 2', title='Mi barrio', start_page=30, end_page=45),
        Chapter(number='Unidad 3', title='De paseo por España', start_page=48, end_page=59)])
    # Der Anhang folgt dem Buch; die Seiten werden hier absichtlich in falscher
    # Reihenfolge eingelesen, sortiert wird nach dem Platz in der Wortliste.
    pages = {172: 'Unidad 2', 171: 'Unidad 1', 173: 'Unidad 3'}
    ids = {p: seed_page(subject="SPANISCH", text="el país — das Land", page=p, label="Schulbuch", title="Vocabulario")
           for p in pages}
    ai_answers(patch,
               {"words": [{"foreign_word": "el país", "meanings": ["das Land"]}]},
               {p: {"ueberschriften": [kopf(name, "el país", groesser=True)],
                    "beginnt_mit_ueberschrift": True} for p, name in pages.items()})
    client.post(V + "/SPANISCH/extract", json={"material_ids": list(ids.values())})
    found = [u["unit"] for u in vocab.units(1, "SPANISCH") if u["words"]]
    # Einheitlich benannt wie im Verzeichnis und in Buchreihenfolge.
    assert found == ['Unidad 1 Hola', 'Unidad 2 Mi barrio', 'Unidad 3 De paseo por España'], found
    # Und unter dem neuen Namen findet der Trainer die Karten der Wortliste.
    assert len(vocab.cards(1, "SPANISCH", "Unidad 3 De paseo por España", 1, "from")) == 1


def test_a_section_runs_across_the_page_break_and_keeps_the_book_order(setup):
    """Im Anhang beginnt ein Abschnitt mitten auf einer Seite und läuft weiter:
    „Story" reicht von der Mitte der S. 218 bis in die obere Hälfte der S. 220.
    Beginnt eine Seite ohne eigene Überschrift, gelten Einheit und Abschnitt der
    Seite davor. Angezeigt wird in der Reihenfolge des Buchs (D115)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    seiten = {218: "Story S. 218", 219: "Story S. 219", 220: "Check-out S. 220"}
    ids = {p: seed_page(subject="ENGLISCH", text=t + "\nword — Wort\nother — anderes",
                        page=p, label="Schulbuch", title="Vocabulary") for p, t in seiten.items()}
    woerter = {"words": [{"foreign_word": "word", "meanings": ["Wort"]},
                         {"foreign_word": "other", "meanings": ["anderes"]}]}
    koepfe = {
        # S. 218: erst noch Station 3, ab dem zweiten Wort beginnt „Story".
        218: {"ueberschriften": [kopf("Vocabulary", wo="seitenkopf"),
                                 kopf("Unit 1", "word", groesser=True),
                                 kopf("Station 3", "word"),
                                 kopf("Story", "other")],
              "beginnt_mit_ueberschrift": True},
        # S. 219 trägt keine eigene Überschrift — sie gehört noch zu „Story".
        219: {"ueberschriften": [kopf("Vocabulary", wo="seitenkopf")],
              "beginnt_mit_ueberschrift": False},
        # S. 220 beginnt ohne Überschrift und wechselt dann zu „Check-out".
        220: {"ueberschriften": [kopf("Vocabulary", wo="seitenkopf"),
                                 kopf("Check-out", "other")],
              "beginnt_mit_ueberschrift": False},
    }
    ai_answers(patch, woerter, koepfe)
    for page in (218, 219, 220):
        client.post(V + "/ENGLISCH/extract", json={"material_ids": [ids[page]]})
    unit = next(u for u in vocab.units(1, "ENGLISCH") if u["words"])
    assert unit["unit"] == "Unit 1" and unit["words"] == 6
    # Abschnitte in Buchreihenfolge, nicht alphabetisch, und „Story" hat die
    # Wörter beider Seiten plus den Rest der Seite davor.
    assert [(s["section"], s["words"]) for s in unit["sections"]] == [
        ("Station 3", 1), ("Story", 4), ("Check-out", 1)]


def test_a_framed_word_field_is_a_block_like_any_other(setup):
    """Die dritte Ebene ist gestrichen. Ob „School" ein Kasten in „The new boy"
    oder ein Abschnitt daneben ist, war die einzige Frage, an der die Gliederung
    noch wackelte — sie hat drei Anläufe gekostet (D124, D135, D136) und für das
    Üben keinen Unterschied gemacht. Ein Kasten ist jetzt ein Block wie jeder
    andere: eine Überschrift, die Wörter darunter (D139)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page(subject="ENGLISCH", text="a — x\nb — y\nc — z\nd — w",
                    page=213, label="Schulbuch", title="Vocabulary")
    ai_answers(patch,
               {"words": [{"foreign_word": w, "meanings": [m]}
                          for w, m in (("a", "x"), ("b", "y"), ("c", "z"), ("d", "w"))]},
               {213: {"ueberschriften": [kopf("Vocabulary", wo="seitenkopf"),
                                         kopf("Unit 1", "a", groesser=True),
                                         kopf("The new boy", "a"),
                                         kopf("School", "b", gerahmt=True),
                                         kopf("Station 1", "d")],
                      "beginnt_mit_ueberschrift": True}})
    client.post(V + "/ENGLISCH/extract", json={"material_ids": [mid]})
    unit = next(u for u in vocab.units(1, "ENGLISCH") if u["words"])
    assert [(s["section"], s["words"]) for s in unit["sections"]] == [
        ("The new boy", 1), ("School", 2), ("Station 1", 1)]
    assert all(not s["boxes"] for s in unit["sections"]), "keine dritte Ebene mehr"
    # Üben lässt sich beides: die ganze Einheit und jeder einzelne Block.
    assert len(vocab.cards(1, "ENGLISCH", "Unit 1", 1, "from")) == 4
    assert len(vocab.cards(1, "ENGLISCH", "Unit 1", 1, "from", section="School")) == 2


def test_the_running_head_of_an_appendix_page_is_no_heading_at_all():
    """Über jeder Anhangseite steht „Vocabulary" und der Name der Einheit. Als
    Überschrift gelesen beginnt dort auf jeder Seite ein neuer Block, und die
    Fortsetzung über den Seitenwechsel reißt ab — bei Josias Englisch landeten
    so dreizehn von sechzehn Seiten in „Unit 1" (D115, D130)."""
    heads = [kopf("Vocabulary", wo="seitenkopf"), kopf("Unit 1", "a", groesser=True),
             kopf("Station 1", "b"), kopf("Media smart", "c", wo="seitenkopf")]
    art = vocab.head_levels(heads, {})
    assert art["vocabulary"] == "laufkopf"
    assert art["unit 1"] == "einheit", "eine Nummer macht die Einheit erkennbar"
    assert art["station 1"] == "abschnitt"
    # „Media smart" trägt keine Nummer, kehrt aber anderswo als Laufkopf wieder:
    # Das ist ein Teil des Buchs, kein Abschnitt in einem.
    assert art["media smart"] == "einheit"
    # Ein Laufkopf schneidet nie, auch die Einheit nicht, die oben wiederholt wird.
    words = [{"plain": "a"}, {"plain": "b"}, {"plain": "c"}]
    cuts = vocab.page_cuts(words, {"ueberschriften": heads, "beginnt_mit_ueberschrift": True}, art)
    assert cuts == [(0, "einheit", "Unit 1"), (1, "abschnitt", "Station 1")]


def test_both_questions_see_the_page_not_only_its_text(setup):
    """Ob eine Überschrift größer, farbig oder gerahmt ist, steht nicht im Text,
    sondern im Satz der Seite. Beide Fragen bekommen deshalb das Bild (D120)."""
    import io
    from PIL import Image
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    blob = io.BytesIO()
    Image.new("RGB", (40, 30), (250, 250, 250)).save(blob, "JPEG")
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE materials SET file_bytes=?,mime_type='image/jpeg',filename='s10.jpg' WHERE id=?",
                  (blob.getvalue(), mid))
    gesehen = []

    async def complete(account, purpose, instruction, context, images=None, *a, **kw):
        gesehen.append(images or [])
        if "subject" not in context:
            return json.dumps({"ueberschriften": []}), {}, "fake"
        return json.dumps(WORDS), {}, "fake"
    patch.setattr(ai, "complete", complete)
    assert client.post(V + "/LATEIN/extract", json={"material_ids": [mid]}).status_code == 200
    assert len(gesehen) == 2, "Wörter und Überschriften, zwei Aufrufe"
    for bilder in gesehen:
        assert len(bilder) == 1 and bilder[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    # Eine Seite ohne hinterlegte Datei wird weiter aus ihrem Text gelesen.
    ohne = seed_page(page=11)
    gesehen.clear()
    assert client.post(V + "/LATEIN/extract", json={"material_ids": [ohne]}).status_code == 200
    assert gesehen[0] == []


def test_the_reading_is_never_told_what_was_open_before(setup):
    """Das Modell bekommt keinen Hinweis mehr darauf, was von der Seite davor
    läuft. Er hieß, ihm die Antwort vorzusagen: Ein schwächeres Modell schrieb
    ihn ab, statt hinzusehen, und ein einziger Fehler wanderte durch alle
    Folgeseiten (D130). Die Fortsetzung stellt jetzt die App her (D139)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    erste = seed_page(page=10, text=PAGE)
    zweite = seed_page(page=11, text=PAGE)
    gesehen = []

    async def complete(account, purpose, instruction, context, *a, **kw):
        gesehen.append(dict(context))
        if "subject" not in context:
            # Die zweite Seite trägt keine eigene Überschrift.
            if context["seite"] == 10:
                return json.dumps({"ueberschriften": [kopf("Lektion 1", "ecce", groesser=True),
                                                      kopf("A", "ecce")],
                                   "beginnt_mit_ueberschrift": True}), {}, "fake"
            return json.dumps({"ueberschriften": [], "beginnt_mit_ueberschrift": False}), {}, "fake"
        return json.dumps({"words": WORDS["words"][:2]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    client.post(V + "/LATEIN/extract", json={"material_ids": [erste]})
    client.post(V + "/LATEIN/extract", json={"material_ids": [zweite]})
    assert not any("offen_von_der_seite_davor" in c for c in gesehen), "kein Hinweis mehr"
    # Und die Fortsetzung stimmt trotzdem: Die zweite Seite gehört noch zu „A".
    lektion = next(u for u in client.get(V + "/LATEIN/units").json()["units"] if u["words"])
    assert lektion["unit"] == "Lektion 1" and lektion["words"] == 4
    assert [(s["section"], s["words"]) for s in lektion["sections"]] == [("A", 4)]


def test_rereading_a_page_clears_what_the_old_reading_left_behind(setup):
    """Ein Wort, das die neue Lesung nicht mehr nennt, gehört nicht mehr zur
    Seite. Blieb es stehen, bildete es mit seiner alten Gliederung einen zweiten
    Abschnitt neben dem berichtigten — „School" mit einem Wort neben „School"
    mit fünfundzwanzig (D122)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    stand = {"n": 0}

    async def complete(account, purpose, instruction, context, *a, **kw):
        if "subject" not in context:
            return json.dumps({"ueberschriften": [kopf("Lektion 1", "ecce", groesser=True),
                                                  kopf("Kasten", "ecce")],
                               "beginnt_mit_ueberschrift": True}), {}, "fake"
        stand["n"] += 1
        return json.dumps({"words": WORDS["words"][:3 if stand["n"] == 1 else 2]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    unit = client.get(V + "/LATEIN/units").json()["units"][0]
    assert [(s["section"], s["words"]) for s in unit["sections"]] == [("Kasten", 3)]
    # Denselben Text noch einmal lesen: Die Seite trägt danach nur noch, was die
    # neue Lesung nennt.
    patch.setattr(vocab, "EXTRACT_VERSION", vocab.EXTRACT_VERSION + 1)
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    unit = client.get(V + "/LATEIN/units").json()["units"][0]
    assert [(s["section"], s["words"]) for s in unit["sections"]] == [("Kasten", 2)]
    with closing(db.webapp_conn()) as c:
        assert "servus" not in {r[0] for r in c.execute("SELECT foreign_word FROM vocab_words")}


def test_the_grouping_can_be_redone_without_touching_a_single_word(setup):
    """Die Gliederung hängt nicht mehr an den Wörtern, sondern an den
    Überschriften. Sie neu zu setzen kostet deshalb keinen Wortaufruf und keinen
    Lernstand — das war die Bedingung, unter der die Bündelung überhaupt neu
    gebaut werden durfte (D125, D139)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    titel = {"jetzt": "Kasten"}
    woerter = {"n": 0}

    async def complete(account, purpose, instruction, context, *a, **kw):
        if "subject" not in context:
            return json.dumps({"ueberschriften": [kopf("Lektion 1", "ecce", groesser=True),
                                                  kopf(titel["jetzt"], "ecce")],
                               "beginnt_mit_ueberschrift": True}), {}, "fake"
        woerter["n"] += 1
        return json.dumps({"words": WORDS["words"][:3]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    with closing(db.webapp_conn()) as c:
        vorher = {r[0]: r[1] for r in c.execute("SELECT id,foreign_word FROM vocab_words")}
    # Das Kind übt eines der Wörter.
    erstes = sorted(vorher)[0]
    client.post(V + "/attempts", json={"word_id": erstes, "stage": 1, "direction": "from",
                                       "answer": "Schau!", "seconds": 3})
    # Nur die Überschriftenfrage wird neu gestellt, die Wörterfrage nicht.
    titel["jetzt"] = "A"
    patch.setattr(vocab, "HEADS_VERSION", vocab.HEADS_VERSION + 1)
    gelesen = woerter["n"]
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert woerter["n"] == gelesen, "die Wörter werden dafür nicht noch einmal gelesen"
    unit = client.get(V + "/LATEIN/units").json()["units"][0]
    assert [(s["section"], s["words"]) for s in unit["sections"]] == [("A", 3)]
    with closing(db.webapp_conn()) as c:
        nachher = {r[0]: r[1] for r in c.execute("SELECT id,foreign_word FROM vocab_words")}
        versuche = [r[0] for r in c.execute("SELECT word_id FROM vocab_attempts")]
    assert nachher == vorher, "dieselben Zeilen, dieselben Wörter"
    assert versuche == [erstes], "und derselbe Lernstand"


def test_a_heading_keeps_its_name_whether_or_not_a_colon_follows():
    """„la fruta:" und „la fruta" sind dieselbe Überschrift; der Doppelpunkt
    kündigt im Buch die Liste an. Ohne das Abschneiden stand jeder Block zweimal
    in der Liste (D124)."""
    found = vocab.clean_heads(vocab.HeadsOut.model_validate({"ueberschriften": [
        {"titel": "la fruta:", "erstes_wort": "la manzana"},
        {"titel": "la fruta", "erstes_wort": "la pera"},
        {"titel": "Unidad 3 ¡Acércate!  ▶ p. 48", "erstes_wort": "el país"}]}))
    # Der Verweis gehört nicht in den Namen der Einheit (D100).
    assert [h["titel"] for h in found["ueberschriften"]] == ["la fruta", "la fruta", "Unidad 3 ¡Acércate!"]


def test_a_block_repeated_at_the_top_of_the_next_page_stays_one_block(setup):
    """Läuft ein Block über den Seitenrand, nennt die Folgeseite seine
    Überschrift oft noch einmal. Dann läuft derselbe Block weiter, statt neben
    sich selbst ein zweites Mal aufzutauchen (D124)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    erste = seed_page(page=10)
    zweite = seed_page(page=11)
    ai_answers(patch,
               {10: {"words": WORDS["words"][:2]}, 11: {"words": WORDS["words"][2:4]}},
               {10: {"ueberschriften": [kopf("Lektion 1", "ecce", groesser=True), kopf("Tiere", "ecce")],
                     "beginnt_mit_ueberschrift": True},
                11: {"ueberschriften": [kopf("Tiere", "servus")], "beginnt_mit_ueberschrift": True}})
    client.post(V + "/LATEIN/extract", json={"material_ids": [erste]})
    client.post(V + "/LATEIN/extract", json={"material_ids": [zweite]})
    unit = client.get(V + "/LATEIN/units").json()["units"][0]
    assert [(s["section"], s["words"]) for s in unit["sections"]] == [("Tiere", 4)]


def test_a_reread_never_costs_a_learned_word_its_history(setup):
    """Die Aufräumregel aus D122 darf keinen Lernstand kosten. Ein geübtes Wort
    bleibt, auch wenn die neue Lesung es nicht mehr nennt, und dieselbe Vokabel
    in neuer Schreibweise behält ihre Zeile samt Verlauf (D125)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    stand = {"n": 0}

    async def complete(account, purpose, instruction, context, *a, **kw):
        if "subject" not in context:
            return json.dumps({"ueberschriften": [kopf("Lektion 1", "ecce", groesser=True)],
                               "beginnt_mit_ueberschrift": True}), {}, "fake"
        stand["n"] += 1
        if stand["n"] == 1:
            return json.dumps({"words": WORDS["words"][:3]}), {}, "fake"
        # Zweite Lesung: „servus" steht mit Marke da, „esse" fehlt ganz.
        return json.dumps({"words": [WORDS["words"][0],
                                     {**WORDS["words"][2], "foreign_word": "servus m."}]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    with closing(db.webapp_conn()) as c:
        ids = {r[1]: r[0] for r in c.execute("SELECT id,foreign_word FROM vocab_words WHERE material_id=?", (mid,))}
    # Das Kind übt zwei der drei Wörter.
    for word in ("servus", "esse"):
        r = client.post(V + "/attempts", json={"word_id": ids[word], "stage": 1, "direction": "from",
                                               "answer": "der Sklave" if word == "servus" else "sein", "seconds": 4})
        assert r.status_code == 200, r.text

    patch.setattr(vocab, "EXTRACT_VERSION", vocab.EXTRACT_VERSION + 1)
    client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    with closing(db.webapp_conn()) as c:
        rows = {r[1]: r[0] for r in c.execute("SELECT id,foreign_word FROM vocab_words WHERE material_id=?", (mid,))}
        versuche = {r[0] for r in c.execute("SELECT word_id FROM vocab_attempts")}
    # Die Marke wandert ins Grammatikfeld; die Zeile bleibt dieselbe.
    assert rows.get("servus") == ids["servus"] and "servus m." not in rows
    # Das geübte, nicht mehr genannte Wort bleibt mitsamt seinem Verlauf.
    assert rows.get("esse") == ids["esse"]
    assert versuche == {ids["servus"], ids["esse"]}
    # Das ungeübte, nicht mehr genannte Wort ist weg.
    assert "cōgitāre" not in rows


def test_an_exercise_number_is_no_heading():
    """Das kleine Modell machte aus der Aufgabennummer „5" einen Abschnitt und
    nahm „Holiday words" damit ein Wort weg (D128). Eine bloße Nummer ist keine
    Überschrift und fällt schon beim Lesen der Überschriften heraus."""
    found = vocab.clean_heads(vocab.HeadsOut.model_validate({"ueberschriften": [
        {"titel": "5"}, {"titel": "2a"}, {"titel": "Nr. 7"}, {"titel": "B3"},
        {"titel": "Holiday words", "erstes_wort": "beach"}]}))
    assert [h["titel"] for h in found["ueberschriften"]] == ["Holiday words"]


def test_two_spellings_of_one_word_do_not_break_the_page(setup):
    """Standen „servus" und „servus m." beide in der alten Lesung, brach die
    Umbenennung aus D125 an der Eindeutigkeit ab — mit ihr die ganze Seite
    (D129). Sie wird jetzt übersprungen, statt alles mitzureißen."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()
    with closing(db.webapp_conn()) as c, c:
        for pos, wort in enumerate(('servus', 'servus m.')):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,position,"
                      "foreign_word,plain,meanings_json,created_at) VALUES(1,'LATEIN',?,'Begleitband',10,'Lektion 1',?,?,?,?,'now')",
                      (mid, pos, wort, vocab.plain(wort), json.dumps(['der Sklave'])))
    ai_answers(patch, {"words": [WORDS["words"][2]]},
               {10: {"ueberschriften": [kopf("Lektion 1", "servus", groesser=True)],
                     "beginnt_mit_ueberschrift": True}})
    r = client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert r.status_code == 200, r.text
    with closing(db.webapp_conn()) as c:
        namen = sorted(x[0] for x in c.execute("SELECT foreign_word FROM vocab_words WHERE material_id=?", (mid,)))
    assert 'servus' in namen


def test_a_double_running_head_is_resolved_by_the_page_itself():
    """„Unit 1 / Media smart" steht über einer Anhangseite, gemeint ist der
    Teil, unter dem die Wörter stehen. Der Titel der Seite sagt es (D130)."""
    assert vocab.split_head('Unit 1 / Media smart', 'Media smart – Searching for information online') == 'Media smart'
    assert vocab.split_head('Welcome back! / Unit 1', 'Welcome back! – Vocabulary') == 'Welcome back!'
    # Ohne Anhaltspunkt wird nicht geraten.
    assert vocab.split_head('Unit 1 / Media smart', '') == 'Unit 1 / Media smart'
    assert vocab.split_head('Unit 1 / Media smart', 'Vocabulary') == 'Unit 1 / Media smart'
    # Ein einfacher Laufkopf bleibt unangetastet, auch mit Bindestrich im Namen.
    assert vocab.split_head('Across cultures 1', 'Vocabulary: Across cultures') == 'Across cultures 1'
def test_the_continuation_stops_at_the_book(setup):
    """Fortgesetzt wird nur innerhalb eines Buchteils. Zwischen Arbeitsheft
    S. 146 und Schulbuch S. 206 liegen zwei Bücher — die Einheit der Heftseite
    wanderte von dort durch den ganzen Anhang (D131)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    heft = seed_page(subject="ENGLISCH", text="a — x", page=146, label="Arbeitsheft", title="Vocabulary")
    buch = seed_page(subject="ENGLISCH", text="b — y", page=206, label="Schulbuch", title="Vocabulary")
    ai_answers(patch,
               {146: {"words": [{"foreign_word": "a", "meanings": ["x"]}]},
                206: {"words": [{"foreign_word": "b", "meanings": ["y"]}]}},
               # Nur die Heftseite nennt eine Einheit; die Buchseite trägt keine.
               {146: {"ueberschriften": [kopf("Unit 1", "a", groesser=True)],
                      "beginnt_mit_ueberschrift": True},
                206: {"ueberschriften": [], "beginnt_mit_ueberschrift": False}})
    client.post(V + "/ENGLISCH/extract", json={"material_ids": [heft, buch]})
    with closing(db.webapp_conn()) as c:
        stand = {r[0]: r[1] for r in c.execute("SELECT page,unit FROM vocab_words WHERE account_id=1")}
    assert stand[146] == "Unit 1"
    assert stand[206] != "Unit 1", "aus einem anderen Buch wird nichts fortgesetzt"


def test_a_unit_boundary_inside_a_page_is_placed_at_the_right_word(setup):
    """Wo zwei Einheiten auf einer Seite aneinanderstoßen, sagt die Überschrift,
    ab welchem Wort der neue Teil gilt: „Holiday words" steht oben auf S. 211
    und gehört noch zu „Welcome back!", darunter beginnt Unit 1 (D132, D139).
    Dass „Welcome back!" ein Teil des Buchs ist und kein Abschnitt, verrät der
    Laufkopf der Seite, der denselben Namen trägt (D130)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    grenze = seed_page(page=11)
    ai_answers(patch, {"words": WORDS["words"][:4]},
               {11: {"ueberschriften": [kopf("Welcome back!", wo="seitenkopf"),
                                        kopf("Welcome back!", "ecce", groesser=True),
                                        kopf("Unit 1", "servus", groesser=True)],
                     "beginnt_mit_ueberschrift": True}})
    client.post(V + "/LATEIN/extract", json={"material_ids": [grenze]})
    with closing(db.webapp_conn()) as c:
        rows = {r[0]: r[1] for r in c.execute("SELECT foreign_word,unit FROM vocab_words WHERE material_id=?", (grenze,))}
    assert rows['ecce'] == 'Welcome back!' and rows['esse'] == 'Welcome back!'
    assert rows['servus'] == 'Unit 1' and rows['cōgitāre'] == 'Unit 1'


def test_unreadable_headings_do_not_cost_the_page(setup):
    """Der Überschriftenlauf ist ein Zugewinn, keine Bedingung: Bleibt er ohne
    Antwort, stehen die Wörter trotzdem da — unter dem Kapitel der Seite. Im
    ersten Lauf mit Eskalation riss der gescheiterte zweite Versuch die Seite
    mit, dreißig von sechsundachtzig (D132)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page()

    async def complete(account, purpose, instruction, context, *a, **kw):
        if "subject" not in context:
            raise RuntimeError('kein Kontingent')
        return json.dumps({"words": WORDS["words"][:2]}), {}, "fake"
    patch.setattr(ai, "complete", complete)
    r = client.post(V + "/LATEIN/extract", json={"material_ids": [mid]})
    assert r.status_code == 200, r.text
    assert list(r.json()["words"].values()) == [2], "die Wörter bleiben stehen"
    unit = next(u for u in vocab.units(1, "LATEIN") if u["words"])
    assert unit["unit"] == "Begleitband S. 10"
    # Der Fehler steht an der Seite und wird nicht ewig wiederholt.
    assert vocab.unread_pages(1, "LATEIN") == []


def test_a_unit_name_carries_no_section_and_the_other_way_round():
    """Der ausführlichere Name gewinnt (D110) — aber nicht, wenn das
    Ausführliche ein Abschnitt dieser Einheit ist. „Unidad 3 De paseo por
    España" ist der Titel der Einheit, „Unit 1 The new boy" die Einheit plus
    einem ihrer Abschnitte (D134)."""
    assert vocab.trim_section_tail('Unit 1 The new boy', ['The new boy', 'Station 1']) == 'Unit 1'
    assert vocab.trim_section_tail('Unidad 3 De paseo por España', ['Texto A']) == 'Unidad 3 De paseo por España'
    # Heißt der Abschnitt wie die ganze Einheit, bleibt der Name stehen.
    assert vocab.trim_section_tail('The new boy', ['The new boy']) == 'The new boy'
    # Und umgekehrt: Die Einheit steht schon über dem Abschnitt.
    assert vocab.trim_unit_prefix('Across cultures 1 London: A first look', 'Across cultures 1') == 'London: A first look'
    assert vocab.trim_unit_prefix('Station 1', 'Unit 1') == 'Station 1'


def test_words_before_the_first_heading_keep_what_was_open():
    """Beginnt die Seite mitten in einem Block, gehören ihre ersten Wörter noch
    dorthin (D115). Steht die erste Überschrift dagegen über dem ersten Wort,
    gilt sie von Anfang an — auch wenn ihr Ankerwort nicht wiederzufinden ist."""
    words = [{"plain": f"w{i}"} for i in range(1, 6)]
    art = {"unit 1": "einheit", "story": "abschnitt"}
    # Mitten im Block: Der Schnitt liegt beim genannten Wort, nicht am Anfang.
    cuts = vocab.page_cuts(words, {"ueberschriften": [kopf("Story", "w3")],
                                   "beginnt_mit_ueberschrift": False}, art)
    assert cuts == [(2, "abschnitt", "Story")]
    # Die Seite beginnt unter der Überschrift: Sie gilt ab dem ersten Wort.
    cuts = vocab.page_cuts(words, {"ueberschriften": [kopf("Story", "w3")],
                                   "beginnt_mit_ueberschrift": True}, art)
    assert cuts == [(0, "abschnitt", "Story")]
    # Ankerwort unauffindbar und die Seite beginnt mittendrin: kein Schnitt,
    # lieber gar keiner als ein falscher.
    cuts = vocab.page_cuts(words, {"ueberschriften": [kopf("Story", "gibtesnicht")],
                                   "beginnt_mit_ueberschrift": False}, art)
    assert cuts == []


def test_a_foreign_part_behind_the_word_list_is_cut_off(setup):
    """Hinter dem Wortschatz beginnt bei Green Line das Dictionary: das gesamte
    Vokabular aller vier Bände, alphabetisch. Auf der Doppelseite 190/191 steht
    beides nebeneinander. Als Wortschatz gelesen schwemmte es die Liste zu —
    Noahs „Unidad 3" hatte 1161 Wörter (D139)."""
    client, state, patch = setup
    client.app.include_router(vocab_router.router, prefix="/api")
    mid = seed_page(subject="ENGLISCH", text="a — x\nb — y\nzebra — Zebra", page=190,
                    label="Schulbuch", title="Vocabulary / Dictionary")
    ai_answers(patch,
               {"words": [{"foreign_word": "a", "meanings": ["x"]},
                          {"foreign_word": "b", "meanings": ["y"]},
                          {"foreign_word": "zebra", "meanings": ["Zebra"]}]},
               {190: {"ueberschriften": [kopf("Vocabulary", wo="seitenkopf"),
                                         kopf("Across cultures 4", "a", groesser=True),
                                         kopf("Dictionary", "zebra", wo="seitenkopf")],
                      "beginnt_mit_ueberschrift": True}})
    client.post(V + "/ENGLISCH/extract", json={"material_ids": [mid]})
    with closing(db.webapp_conn()) as c:
        namen = sorted(r[0] for r in c.execute("SELECT foreign_word FROM vocab_words"))
    assert namen == ["a", "b"], "was unter dem Dictionary steht, gehört nicht in die Liste"


def test_a_spread_delivered_twice_is_read_only_once():
    """Noahs Englischbuch kommt als Doppelseite, und der Viewer liefert nicht
    immer, was bestellt wurde: Vierzig Abrufe deckten fünfzehn Doppelseiten ab,
    jede zwei- bis dreimal. Jede Dublette brachte dieselben Wörter noch einmal
    unter einer anderen Seitenzahl und riss die Fortsetzung auseinander (D138)."""
    rows = [
        {"id": 260, "source_page": 162, "source_label": "Schulbuch", "printed_pages": "[162, 163]", "page_check": "ok"},
        {"id": 261, "source_page": 158, "source_label": "Schulbuch", "printed_pages": "[158, 159]", "page_check": "ok"},
        {"id": 265, "source_page": 167, "source_label": "Schulbuch", "printed_pages": "[162, 163]", "page_check": "mismatch"},
    ]
    behalten = [r["id"] for r in vocab.one_per_spread(rows)]
    assert behalten == [261, 260], "die Dublette fällt weg, der Rest steht in Buchreihenfolge"


def test_a_spread_nobody_else_delivered_is_kept_even_if_it_was_not_ordered():
    """Die falsche Lieferung ist die einzige Quelle ihrer gedruckten Seiten —
    sie wegzuwerfen hieße, die Seiten gar nicht zu lesen (D138)."""
    rows = [
        {"id": 260, "source_page": 162, "source_label": "Schulbuch", "printed_pages": "[162, 163]", "page_check": "ok"},
        {"id": 261, "source_page": 163, "source_label": "Schulbuch", "printed_pages": "[158, 159]", "page_check": "mismatch"},
    ]
    assert [r["id"] for r in vocab.one_per_spread(rows)] == [261, 260]
    # Ohne Angabe gilt die bestellte Seite, und zweimal dieselbe ist eine Dublette.
    ohne = [{"id": 1, "source_page": 12, "source_label": "", "printed_pages": None, "page_check": "unknown"},
            {"id": 2, "source_page": 12, "source_label": "", "printed_pages": "", "page_check": "unknown"}]
    assert [r["id"] for r in vocab.one_per_spread(ohne)] == [1]
    assert vocab.printed_of({"source_page": 12, "printed_pages": "kaputt"}) == [12]


def test_the_words_of_a_doubled_page_go_but_a_practised_one_stays(setup):
    """Die Dublette nur beim Lesen zu überspringen genügt nicht: Die Einheiten
    zählen Wörter, nicht Seiten. Geübtes bleibt trotzdem stehen (D125/D138)."""
    client, state, patch = setup
    with closing(db.webapp_conn()) as c, c:
        c.execute("DELETE FROM vocab_words WHERE account_id=1")
        c.execute("DELETE FROM materials WHERE account_id=1 AND lower(subject_name)='englisch'")
    echt = seed_page(subject="ENGLISCH", page=162, label="Schulbuch", title="Vocabulary")
    doppelt = seed_page(subject="ENGLISCH", page=167, label="Schulbuch", title="Vocabulary")
    with closing(db.webapp_conn()) as c, c:
        for mid, check in ((echt, 'ok'), (doppelt, 'mismatch')):
            c.execute("UPDATE materials SET printed_pages='[162, 163]',page_check=? WHERE id=?", (check, mid))
        for mid, wort in ((echt, 'echt'), (doppelt, 'dublette'), (doppelt, 'geuebt')):
            c.execute("INSERT INTO vocab_words(account_id,subject,material_id,source_label,page,unit,section,position,"
                      "foreign_word,plain,meanings_json,created_at) VALUES(1,'ENGLISCH',?,'Schulbuch',162,'Unit 1','',0,?,?,'[]','now')",
                      (mid, wort, wort))
        wid = c.execute("SELECT id FROM vocab_words WHERE foreign_word='geuebt'").fetchone()[0]
        c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,spoken,seconds,edits,created_at) "
                  "VALUES(1,?,1,'from','x','correct',0,3,0,'now')", (wid,))
    assert vocab.forget_duplicates(1, 'ENGLISCH') == 1
    with closing(db.webapp_conn()) as c:
        blieb = {r[0] for r in c.execute("SELECT foreign_word FROM vocab_words WHERE account_id=1 AND subject='ENGLISCH'")}
    assert blieb == {'echt', 'geuebt'}
    assert vocab.forget_duplicates(1, 'ENGLISCH') == 0, "ein zweiter Lauf fasst nichts mehr an"


def test_the_same_page_number_in_two_books_is_not_a_duplicate():
    """Seitenzahlen gelten nur innerhalb eines Buches: Begleitband S. 10 und
    Arbeitsheft S. 10 sind zwei Seiten, keine Dublette (D138)."""
    rows = [
        {"id": 1, "source_page": 10, "source_label": "Begleitband", "printed_pages": "[10]", "page_check": "ok"},
        {"id": 2, "source_page": 10, "source_label": "Arbeitsheft", "printed_pages": "[10]", "page_check": "ok"},
        {"id": 3, "source_page": 10, "source_label": "", "origin": "book_fetch", "printed_pages": "[10]", "page_check": "ok"},
        {"id": 4, "source_page": 10, "source_label": "Schulbuch", "printed_pages": "[10]", "page_check": "ok"},
    ]
    # Drei Bücher: Begleitband, Arbeitsheft und das Schulbuch — die Abholung ohne
    # Etikett ist dasselbe Buch wie „Schulbuch" und damit die einzige Dublette.
    assert [r["id"] for r in vocab.one_per_spread(rows)] == [2, 1, 3]
