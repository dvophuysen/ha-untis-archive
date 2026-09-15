"""Paket 3: Einträge ohne Quelle, Fachgewohnheit, Foto-Aufforderung."""
import json
import sqlite3
from contextlib import closing

from test_learning import env  # noqa: F401
from test_sources import history, LA, SN
from test_source_collector import shelf
from test_book_structure import chapters_fixture
from backend import book_structure as bs, db, sources
from backend.book_structure import Chapter


def test_a_unit_number_in_the_text_names_the_chapter_without_a_model(env):
    shelf()
    chapters_fixture()
    chapters = bs.chapters_of(1, "¡Apúntate! 2")
    assert bs.rule_match("Wortschatztraining Lektion 3, Übungen zu ser/estar", chapters)["title"] == "¡Acércate!"
    assert bs.rule_match("Unidad 2 wiederholen", chapters)["title"] == "Mi barrio"
    assert bs.rule_match("Lektion 2 und 3", chapters) is None, "zwei Nummern sind keine Zuordnung"
    assert bs.rule_match("Übungen zur 3. Person", chapters) is None


async def test_entries_without_a_page_are_mapped_to_a_chapter_and_the_chapter_is_collected(env, monkeypatch):
    history(lessons=[(1, '2026-09-08', 'SPANISCH', SN, 'Lektion 3: Wortschatz Stadt'),
                     (2, '2026-09-09', 'SPANISCH', SN, 'Übungen zu ser und estar'),
                     (3, '2026-09-10', 'SPANISCH', SN, 'Klassenfahrt: Organisation')])
    shelf()
    chapters_fixture()
    with closing(db.webapp_conn()) as conn:
        conn.execute("UPDATE digital_textbook_access SET toc_state='ready'")
        conn.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) VALUES(1,'2026/27',8,1,1,'now')")
    asked = []

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
        asked.append((purpose, [n["text"] for n in context["notizen"]]))
        gramatica = next(c["chapter_id"] for c in context["inhaltsverzeichnis"] if c["titel"] == "Gramática")
        return json.dumps({"items": [{"id": 0, "chapter_id": gramatica, "confidence": 0.8},
                                     {"id": 1, "chapter_id": None, "confidence": 0.1}]}), 0, 0
    monkeypatch.setattr(bs.ai, "complete", complete)
    summary = await bs.map_entries(1)
    assert summary == {"rule": 1, "ai": 1, "none": 1, "asked": 2}
    assert asked == [("sources", ["Übungen zu ser und estar", "Klassenfahrt: Organisation"])], "die Lektionsnummer braucht kein Modell"
    # Nichts wird zweimal gefragt.
    assert await bs.map_entries(1) == {"rule": 0, "ai": 0, "none": 0, "asked": 0}
    sources.sync_links(1)
    book = sources.ledger(1)["subjects"][0]
    titles = {(c["title"], c["inferred"]) for c in book["chapters"]}
    assert titles == {("¡Acércate!", True), ("Gramática", True)}
    assert book["pending"] == 14 + 5, "die ganze Einheit samt Vokabelteil wird geholt, als Hypothese gekennzeichnet"
    with closing(db.webapp_conn()) as conn:
        quote = conn.execute("SELECT quote FROM source_links WHERE page=48").fetchone()[0]
    assert "erschlossen" in quote


def test_a_teacher_who_always_writes_ah_means_the_workbook(env):
    history(homework=[(1, 'LA', 'AH S. 5 Aufg. 1', '2026-09-01'), (2, 'LA', 'AH S. 7 Aufg. C', '2026-09-03'),
                      (3, 'LA', 'Arbeitsheft S. 9', '2026-09-05'), (4, 'LA', 'S. 12 Nr. 3', '2026-09-08')])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'la','Prima','now')")
    only = sources.ledger(1)["subjects"][0]
    assert only["pending"] == 0, "das nackte „S. 12“ wird nicht als Schulbuch geholt"
    reasons = {(m["label"], m["reason"], tuple(m["pages"])) for m in only["missing"]}
    assert ("Unbekannte Quelle", "gewohnheit", (12,)) in reasons
    assert ("Arbeitsheft", "paper", (5, 7, 9)) in reasons


def test_photo_requests_only_before_an_exam_and_at_most_three(env):
    history(homework=[(1, 'SN', '#cda, p. 26-28', '2026-09-10'), (2, 'SN', 'Grammatikheft S. 18', '2026-09-11'),
                      (3, 'LA', 'AH S. 7', '2026-09-11'), (4, 'SN', 'Arbeitsblatt S. 2', '2026-09-12')])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'sn','¡Apúntate! 2','now')")
    sources.ledger(1)
    assert sources.photo_requests(1, [], "2026-09-15") == [], "ohne Arbeit wird nichts eingefordert"
    exams = [{"subject_name": "SN", "date": "2026-09-24"}, {"subject_name": "LA", "date": "2026-11-02"}]
    asks = sources.photo_requests(1, exams, "2026-09-15")
    assert [a["subject"] for a in asks] == ["SN", "SN", "SN"], "höchstens drei, nur das Fach mit der Arbeit in zwei Wochen"
    assert asks[0]["label"] == "Arbeitsheft" and asks[0]["pages_label"] == "S. 26–28" and asks[0]["exam_date"] == "2026-09-24"
    assert "cda" in asks[0]["quote"]
