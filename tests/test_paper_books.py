"""Zwei Bücher in einem Fach, Papierbücher mit fotografiertem Verzeichnis und
der Zettel der Lehrkraft mit dem Klausurstoff.

Der Beispieltext ist Kind B Notiz zur ersten Lateinarbeit, wörtlich."""
import asyncio
import io
import json
import sqlite3
from contextlib import closing

from PIL import Image

from test_learning import env, child
from test_sources import history, LA
from backend import db, sources, book_structure as bs, material_analysis as analysis
from backend.routers import materials as materials_routes, subjects as subjects_routes

NOTE = ("Voc. 1. Lektion S. 10, 11\nSubstantive: a/o-Deklination BB. S. 13\nVerben a/e/i-Konjugation BB S. 13-15\n"
        "Subjekt im Prädikat BB. S. 14\nGefahr im C.M. TB S. 10, 11, 14, 15")


def photo(width=900):
    out = io.BytesIO()
    Image.new("RGB", (width, 600), (250, 250, 250)).save(out, "JPEG")
    return out.getvalue()


def test_latin_has_two_books_and_a_page_list_reads_every_number():
    got = [(c["label"], c["pages"]) for c in sources.citations(NOTE)]
    assert got == [("Unbekannte Quelle", [10, 11]), ("Begleitband", [13]), ("Begleitband", [13, 14, 15]),
                   ("Begleitband", [14]), ("Textband", [10, 11, 14, 15])]
    # Eine Aufzählung endet, wo die Zahl nicht mehr aufsteigt oder eine Aufgabe ist.
    assert sources.citations("S. 12, 3a lösen")[0]["pages"] == [12]
    assert sources.citations("S. 34, 5 Sätze")[0]["pages"] == [34]
    # Der Textband ist das Schulbuch; der Begleitband ein anderes Buch.
    assert sources.serves("Schulbuch", "Textband") and sources.serves("", "Textband") and sources.serves("Textband", "")
    assert not sources.serves("Begleitband", "Textband") and not sources.serves("", "Begleitband")
    assert sources.serves("Begleitband", "Begleitband") and sources.serves("Begleitband", "Unbekannte Quelle")
    assert sources.book_serves("Pontes Textband", "Textband") and not sources.book_serves("Pontes Textband", "Begleitband")
    assert sources.book_serves("Pontes Begleitband", "Begleitband") and not sources.book_serves("Pontes Begleitband", "Textband")


def test_a_begleitband_scan_settles_only_the_begleitband_page(env):
    history(homework=[(1, "LA", "BB S. 13 lernen", "2026-09-07"), (2, "LA", "TB S. 13 Aufg. C", "2026-09-08")])
    missing = {m["label"]: m["pages"] for m in sources.ledger(1)["subjects"][0]["missing"]}
    assert missing == {"Begleitband": [13], "Textband": [13]}
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,created_at,updated_at) "
                  "VALUES(1,'book_page','LA','Seite 13','Begleitband',13,'now','now')")
    missing = {m["label"]: m["pages"] for m in sources.ledger(1)["subjects"][0]["missing"]}
    assert missing == {"Textband": [13]}, "die Begleitband-Seite belegt keine Textband-Seite"
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_page,created_at,updated_at) "
                  "VALUES(1,'book_page','LA','Seite 13',13,'now','now')")
    assert sources.ledger(1)["missing_total"] == 0, "ohne Buchteil gilt das Hauptbuch"


def test_a_workbook_photo_with_a_printed_page_is_the_workbook(env):
    history(homework=[(1, "LA", "AH S. 7 Aufg. C", "2026-09-07"), (2, "LA", "TB S. 7", "2026-09-08")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_page,created_at,updated_at) "
                  "VALUES(1,'workbook','LA','Übung','7','now','now')")
    missing = {m["label"]: m["pages"] for m in sources.ledger(1)["subjects"][0]["missing"]}
    assert missing == {"Textband": [7]}, "die Heftseite belegt das Heft, nicht das Buch"


def test_the_analysis_reads_the_printed_page_off_a_manual_scan(env):
    # Die von Hand gescannte Seite 19 stand weiter auf der Liste, weil nur ihr
    # Text gelesen wurde. Jetzt merkt sich die Datei ihre Seite und den Teil.
    history(homework=[(1, "LA", "Textband Seite 19 Aufgabe A3, für die Klassenarbeit lernen", "2026-09-14")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','LA','image.jpg','Lektion 2 … 19','ready','now','now')")
    assert sources.ledger(1)["missing_total"] == 1, "ein Verweis im Text belegt keine Seite"
    with closing(db.webapp_conn()) as c, c:
        row = c.execute("SELECT * FROM materials").fetchone()
        analysis._apply(c, 1, row, analysis.Insight(kind="book_page", content_text="Text", printed_pages=[19], book_part="Textband", confidence=0.9))
        row = c.execute("SELECT source_page,source_label FROM materials").fetchone()
    assert tuple(row) == (19, "Textband")
    assert sources.ledger(1)["missing_total"] == 0


def test_an_exam_notice_is_a_source_with_priority(env):
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,document_date,analysis_state,created_at,updated_at) "
                  "VALUES(1,'exam_notice','LATEIN','Zettel zur Arbeit',?,'2026-09-14','ready','now','now')", (NOTE,))
    book = sources.ledger(1)
    latin = book["subjects"][0]
    assert latin["subject"] == "LATEIN"
    missing = {(m["label"], tuple(m["pages"])) for m in latin["missing"]}
    assert ("Begleitband", (13, 14, 15)) in missing and ("Textband", (10, 11, 14, 15)) in missing
    with closing(db.webapp_conn()) as c:
        kinds = {r[0] for r in c.execute("SELECT DISTINCT entry_kind FROM source_links")}
    assert kinds == {"exam_notice"}
    from backend import source_collector as collector
    priority = asyncio.run(collector.priorities(1))
    assert ("latein", 13) in priority["homework_pages"], "der Zettel zählt wie eine offene Hausaufgabe"
    # Ein Begleitband-Foto der Seite 14 streicht zwei Nennungen auf einmal.
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','BB S. 14','Begleitband',14,'now','now')")
    latin = sources.ledger(1)["subjects"][0]
    assert latin["scanned"] == 1
    assert {(m["label"], tuple(m["pages"])) for m in latin["missing"]} >= {("Begleitband", (13, 15)), ("Textband", (10, 11, 14, 15))}


def test_a_paper_book_gets_the_chapter_rule_from_its_photographed_contents(env, monkeypatch):
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")], homework=[(1, "LA", "BB S. 13 Verben lernen", "2026-09-07")])
    with closing(db.webapp_conn()) as c:
        for page in (2, 3):
            c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,file_bytes,mime_type,created_at,updated_at) "
                      "VALUES(1,'toc','LATEIN','Inhalt','Begleitband',?,?,'image/jpeg','now','now')", (page, photo()))

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
        # Zwei Fotos werden zu einem Bild; fünf Verzeichnisseiten passen in einen Aufruf.
        assert "Inhaltsverzeichnis" in instruction and len(images) == 1 and context["buch"] == "Begleitband Latein"
        return json.dumps({"is_toc": True, "continues": False, "chapters": [
            {"number": "1", "title": "Wortschatz", "start_page": 10, "level": 1},
            {"number": "2", "title": "Wortschatz", "start_page": 16, "level": 1},
            {"number": "", "title": "Formentabellen", "start_page": 206, "kind": "appendix"}]}), 0, 0
    monkeypatch.setattr(bs.ai, "complete", complete)
    result = asyncio.run(bs.read_paper_toc(1, "LATEIN", "Begleitband"))
    assert (result["state"], result["chapters"]) == ("read", 3)
    assert [p["part_label"] for p in bs.paper_books(1, "LATEIN")] == ["Begleitband"]

    latin = sources.ledger(1)["subjects"][0]
    missing = {m["label"]: m["pages"] for m in latin["missing"]}
    assert missing == {"Begleitband": [10, 11, 12, 13, 14, 15]}, "die ganze Lektion, nicht nur die genannte Seite"
    assert [(c["part_label"], c["number"], c["pages_stored"]) for c in latin["chapters"]] == [("Begleitband", "1", 0)]
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','BB S. 12','Begleitband',12,'now','now')")
    latin = sources.ledger(1)["subjects"][0]
    assert latin["chapters"][0]["pages_stored"] == 1
    assert {m["label"]: m["pages"] for m in latin["missing"]} == {"Begleitband": [10, 11, 13, 14, 15]}
    books = {b["title"]: b for b in sources.ledger(1)["books"]}
    assert books["Begleitband Latein"]["pages_stored"] == 1 and books["Begleitband Latein"]["access"]["status"] == "paper"
    # Der Klausurstoff kennt das Kapitel des Papierbuchs.
    from backend import exam_scope
    chapters = exam_scope.book_chapters(1, "LATEIN", "2026-09-01", "2026-09-30")
    assert [(c["part_label"], c["title"]) for c in chapters] == [("Begleitband", "Wortschatz")]


def test_uploads_carry_the_timetable_spelling_and_their_book_part(env):
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")
    client.app.include_router(subjects_routes.router, prefix="/api")
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")])
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("UPDATE lessons SET subject_untis_id=7")
    reply = client.post("/api/accounts/1/materials", files={"file": ("bb.jpg", photo(), "image/jpeg")},
                        data={"subject_name": "Latein", "kind": "book_page", "source_label": "Begleitband", "source_page": "14"})
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert (body["subject_name"], body["kind"], body["source_label"], body["source_page"]) == ("LATEIN", "book_page", "Begleitband", 14)
    assert body["title"] == "Begleitband S. 14"
    fixed = client.patch(f"/api/accounts/1/materials/{body['id']}", json={"subject_name": "latein", "source_label": "Textband", "source_page": 0})
    assert fixed.status_code == 200, fixed.text
    assert (fixed.json()["subject_name"], fixed.json()["source_label"], fixed.json()["source_page"]) == ("LATEIN", "Textband", None)
    assert client.post("/api/accounts/1/materials", files={"file": ("x.jpg", photo(), "image/jpeg")},
                       data={"source_label": "Heftchen"}).status_code == 422
    catalog = client.get("/api/accounts/1/subjects").json()["subjects"]
    assert [(s["name"], s["untis_name"]) for s in catalog] == [("Latein", "LATEIN")]
