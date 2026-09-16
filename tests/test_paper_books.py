"""Zwei Bücher in einem Fach, Papierbücher mit fotografiertem Verzeichnis und
der Zettel der Lehrkraft mit dem Klausurstoff.

Der Beispieltext ist die Notiz eines Kindes zur ersten Lateinarbeit, wörtlich."""
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


def test_a_photographed_double_page_settles_both_pages(env):
    history(homework=[(1, "LA", "TB S. 10, 11 lesen", "2026-09-07")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,printed_pages,created_at,updated_at) "
                  "VALUES(1,'book_page','LA','Gefahr im Circus Maximus','Textband',10,'[10, 11]','now','now')")
    assert sources.ledger(1)["missing_total"] == 0


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
        # Jedes Foto für sich; fünf Verzeichnisseiten passen in einen Aufruf.
        assert "Inhaltsverzeichnis" in instruction and len(images) == 2 and context["buch"] == "Begleitband Latein"
        assert purpose == "sources"
        # Der Begleitband nennt jede Lektion „Wortschatz"; das Modell hält sie
        # für Vokabelteile. Nummeriert und oben heißt trotzdem Kapitel.
        return json.dumps({"is_toc": True, "continues": False, "chapters": [
            {"number": "1", "title": "Wortschatz", "start_page": 10, "level": 1, "kind": "vocab"},
            {"number": "2", "title": "Wortschatz", "start_page": 16, "level": 1, "kind": "vocab"},
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
    assert [(u["number"], u["kind"]) for u in books["Begleitband Latein"]["units"]] == [("1", "chapter"), ("2", "chapter"), ("", "appendix")]
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


def test_an_unnumbered_part_heading_is_not_a_chapter(env):
    # Der Textband beginnt jeden Teil mit zwei Einführungsseiten; „Gefahr im
    # Circus Maximus" (S. 10–29) überschreibt die Lektionen 1 bis 3. Eine
    # Nennung der Einführungsseite holt nicht zwanzig Seiten.
    from backend.book_structure import Chapter, store_chapters, chapter_of, chapters_of
    title = bs.paper_title("LATEIN", "Textband")
    store_chapters(1, title, [
        Chapter(number="", title="Gefahr im Circus Maximus", start_page=10, level=1),
        Chapter(number="1", title="Incitatus soll ein Star werden!", start_page=12, level=2),
        Chapter(number="2", title="Nur Augen für Afra?", start_page=18, level=2),
        Chapter(number="3", title="Ein Fest", start_page=24, level=2),
        Chapter(number="", title="Götter, Tempel und Feste", start_page=30, level=1),
        Chapter(number="4", title="Ein Opfer", start_page=32, level=2),
    ])
    chapters = chapters_of(1, title)
    assert chapter_of(chapters, 10) is None
    assert chapter_of(chapters, 19)["number"] == "2"
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO paper_books(account_id,subject_name,part_label,title,toc_state,updated_at) "
                  "VALUES(1,'LATEIN','Textband',?,'read','now')", (title,))
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "TB S. 10, 11 und S. 19")])
    latin = sources.ledger(1)["subjects"][0]
    assert [(c["number"], c["start_page"], c["end_page"]) for c in latin["chapters"]] == [("2", 18, 23)]
    assert {m["label"]: m["pages"] for m in latin["missing"]} == {"Textband": [10, 11, 18, 19, 20, 21, 22, 23]}


def test_the_exam_card_knows_what_material_is_there_and_what_is_missing(env):
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")],
            homework=[(1, "LA", "BB S. 13 lernen", "2026-09-07"), (2, "LA", "TB S. 13 Aufg. C", "2026-09-08")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','BB S. 13','Begleitband',13,'ready','now','now')")
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,document_date,analysis_state,created_at,updated_at) "
                  "VALUES(1,'exam_notice','LATEIN','Zettel',?,'2026-09-14','ready','now','now')", (NOTE,))
    # Der Zehn-Minuten-Takt des Abgleichs gilt je Prozess; hier ist die Datenbank neu.
    sources._SYNCED.clear()
    got = sources.exam_sources(1, "LATEIN", "2026-08-01", "2026-09-30")
    assert got["notice"] and got["ready"] == 1 and got["missing"] >= 1
    assert {m["label"] for m in got["missing_items"]} == {"Textband", "Unbekannte Quelle", "Begleitband"}
    # Vor dem Zeitraum genannt zählt nicht; ohne Stellen und Zettel gibt es nichts zu zeigen.
    assert sources.exam_sources(1, "LATEIN", "2026-09-20", "2026-09-30") is None
    assert sources.exam_sources(1, "", "2026-08-01", "2026-09-30") is None


def test_background_work_does_not_eat_the_childs_daily_budget(env, monkeypatch):
    from backend import ai_gateway as ai
    from fastapi import HTTPException
    import pytest
    for k, v in {'LEARNING_AI_MODEL': 'test', 'LEARNING_AI_URL': 'https://example.com/responses', 'LEARNING_AI_KEY': 'fake'}.items():
        monkeypatch.setenv(k, v)
    with closing(db.webapp_conn()) as c, c:
        ai.init_config(c)
        c.execute("UPDATE mentor_ai_config SET monthly_micro=50000000, sources_micro=30000000, background_micro=10000000, opening_confirmed=1")
        # Ein Nachmittag Quellenbestand und Auswertung für dieses Kind: 9,50 Euro.
        for purpose, micro in (("sources", 6_000_000), ("background", 3_500_000)):
            c.execute("INSERT INTO mentor_ai_calls(id,account_id,session_id,purpose,month,day,model,status,reserved_micro,charged_micro,input_rate,output_rate,created_at) "
                      "VALUES(?,1,NULL,?,'2026-09','2026-09-11','test','settled',?,?,10,45,'now')", (purpose, purpose, micro, micro))
    key = ai.reserve(1, "mentor", None, 1000, 500)
    assert key, "das Kind darf fragen, obwohl die App heute schon gearbeitet hat"
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO mentor_ai_calls(id,account_id,session_id,purpose,month,day,model,status,reserved_micro,charged_micro,input_rate,output_rate,created_at) "
                  "VALUES('own',1,NULL,'mentor','2026-09','2026-09-11','test','settled',9990000,9990000,10,45,'now')")
    with pytest.raises(HTTPException) as caught:
        ai.reserve(1, "mentor", None, 1000, 500)
    assert caught.value.status_code == 429 and "heute" in caught.value.detail


def test_a_page_without_book_part_is_guessed_from_the_touched_chapter(env):
    # „Voc. 1. Lektion S. 10, 11" nennt kein Buch. Lektion 1 des Begleitbands
    # (S. 10–15) ist angeschnitten, der Textband beginnt erst auf S. 12.
    from backend.book_structure import Chapter, store_chapters
    for label, chapters in (("Begleitband", [Chapter(number="1", title="Wortschatz", start_page=10, level=1),
                                             Chapter(number="2", title="Wortschatz", start_page=16, level=1)]),
                            ("Textband", [Chapter(number="1", title="Incitatus", start_page=12, level=1),
                                          Chapter(number="2", title="Afra", start_page=18, level=1)])):
        title = bs.paper_title("LATEIN", label)
        store_chapters(1, title, chapters)
        with closing(db.webapp_conn()) as c:
            c.execute("INSERT INTO paper_books(account_id,subject_name,part_label,title,toc_state,updated_at) VALUES(1,'LATEIN',?,?,'read','now')", (label, title))
    # Der zuletzt genannte Buchteil gilt im selben Text weiter; die Vokabelseite
    # steht deshalb in einem eigenen Eintrag ohne Buchteil.
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "BB S. 13 Verben"), (2, "2026-09-12", "LATEIN", LA, "Vokabeln S. 10, 11 lernen")])
    latin = sources.ledger(1)["subjects"][0]
    unknown = [m for m in latin["missing"] if m["label"] == "Unbekannte Quelle"]
    assert unknown and unknown[0]["pages"] == [10, 11] and unknown[0]["guess"] == "Begleitband"
    # Seite 13 steht in beiden Büchern in einer Lektion, aber nur der Begleitband ist angeschnitten.
    assert sources._book_guesser(1, "LATEIN")(13) == "Begleitband"
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO source_links(account_id,entry_kind,entry_id,entry_date,subject_name,part_label,part_kind,page,quote,synced_at,updated_at) "
                  "VALUES(1,'homework',9,'2026-09-12','LATEIN','Textband','book',13,'TB S. 13','2099','2099')")
    assert sources._book_guesser(1, "LATEIN")(13) is None, "zwei angeschnittene Kapitel sind keine Antwort"


def test_readings_with_consequences_ask_to_be_checked(env):
    from backend import materials as store
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,document_date,analysis_state,confidence,created_at,updated_at) "
                  "VALUES(1,'exam_notice','LATEIN','Zettel',?,'2026-09-14','ready',0.9,'now','now')", (NOTE,))
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,confidence,created_at,updated_at) "
                  "VALUES(1,'worksheet','LATEIN','Blatt','ready',0.4,'now','now')")
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,analysis_state,confidence,created_at,updated_at) "
                  "VALUES(1,'worksheet','LATEIN','Sicheres Blatt','ready',0.95,'now','now')")
    rows = {m["title"]: m for m in client.get("/api/accounts/1/materials?books=false").json()["materials"]}
    assert rows["Zettel"]["needs_review"] and rows["Blatt"]["needs_review"] and not rows["Sicheres Blatt"]["needs_review"]
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")])
    sources._SYNCED.clear()
    card = sources.exam_sources(1, "LATEIN", "2026-08-01", "2026-09-30")
    assert card["notice"] and card["notice_verified"] is False and card["notice_text"].startswith("Voc. 1. Lektion")
    client.post(f"/api/accounts/1/materials/{rows['Zettel']['id']}/verified", json={"value": True})
    assert sources.exam_sources(1, "LATEIN", "2026-08-01", "2026-09-30")["notice_verified"] is True
    assert not [m for m in client.get("/api/accounts/1/materials?books=false").json()["materials"] if m["title"] == "Zettel"][0]["needs_review"]


def test_the_notice_rule_only_joins_the_grouping_when_a_notice_is_present():
    from backend import exam_scope
    assert exam_scope.Group(category="context", title="Nicht angekündigt", detail="Behandelt, nicht genannt", ids=[1])
    assert "Offizielle Themenliste" in exam_scope.NOTICE_RULE and "Zettel" not in exam_scope.NOTICE_PREFIX


def test_photographed_contents_serve_the_digital_book_whose_contents_were_not_found(env, monkeypatch):
    # Spanisch hat ein digitales Buch, dessen Verzeichnis der Abruf auf den
    # Seiten 2 bis 9 nicht fand. Fotos der Inhaltsseiten gelten dann für
    # dieses Buch, und der Sammellauf holt danach ganze Kapitel.
    history(lessons=[(1, "2026-09-11", "SPANISCH", '{"su": [{"name": "SN"}]}', "Repaso (#libro, p. 50)")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'spanisch','¡Apúntate! 2','now')")
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,file_bytes,mime_type,created_at,updated_at) "
                  "VALUES(1,'toc','SPANISCH','Inhalt','Schulbuch',2,?,'image/jpeg','now','now')", (photo(),))

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
        assert context["buch"] == "¡Apúntate! 2"
        return json.dumps({"is_toc": True, "continues": False, "chapters": [
            {"number": "Unidad 3", "title": "¡Acércate!", "start_page": 48, "level": 1},
            {"number": "Unidad 4", "title": "De viaje", "start_page": 62, "level": 1}]}), 0, 0
    monkeypatch.setattr(bs.ai, "complete", complete)
    result = asyncio.run(bs.read_paper_toc(1, "SPANISCH", "Schulbuch"))
    assert result["digital"] and result["title"] == "¡Apúntate! 2" and result["chapters"] == 2
    assert bs.toc_state(1, "¡Apúntate! 2") == "ready", "der Sammellauf sucht das Verzeichnis nicht mehr"
    assert bs.paper_books(1, "SPANISCH") == []
    spanish = sources.ledger(1)["subjects"][0]
    assert [(c["number"], c["pages"]) for c in spanish["chapters"]] == [("Unidad 3", 14)]
    assert spanish["pending"] == 14, "die ganze Unidad wird geholt, nicht nur Seite 50"


def test_a_corrected_chapter_keeps_its_pages_through_a_new_reading(env):
    from backend.book_structure import Chapter, store_chapters, update_chapter, chapters_of
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")
    title = bs.paper_title("LATEIN", "Begleitband")
    reading = [Chapter(number="10", title="Wortschatz", start_page=64, level=1),
               Chapter(number="11", title="Wortschatz", start_page=69, level=1),
               Chapter(number="12", title="Wortschatz", start_page=75, level=1),
               Chapter(number="13", title="Wortschatz", start_page=84, level=1)]
    store_chapters(1, title, reading)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO paper_books(account_id,subject_name,part_label,title,toc_state,updated_at) VALUES(1,'LATEIN','Begleitband',?,'read','now')", (title,))
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "BB S. 70")])
    by_number = {c["number"]: c for c in chapters_of(1, title)}
    assert (by_number["10"]["end_page"], by_number["11"]["start_page"]) == (68, 69)
    # Lektion 11 beginnt laut Foto auf S. 70, das Modell las 69.
    reply = client.patch(f"/api/accounts/1/materials/sources/chapters/{by_number['11']['id']}", json={"start_page": 70})
    assert reply.status_code == 200, reply.text
    by_number = {c["number"]: c for c in chapters_of(1, title)}
    assert (by_number["10"]["end_page"], by_number["11"]["start_page"], by_number["11"]["end_page"]) == (69, 70, 74)
    assert by_number["11"]["locked"] == 1
    # Rückt der Nachbar, rückt das nicht ausdrücklich gesetzte Ende mit.
    client.patch(f"/api/accounts/1/materials/sources/chapters/{by_number['12']['id']}", json={"start_page": 76})
    by_number = {c["number"]: c for c in chapters_of(1, title)}
    assert (by_number["11"]["end_page"], by_number["12"]["start_page"]) == (75, 76)
    client.patch(f"/api/accounts/1/materials/sources/chapters/{by_number['12']['id']}", json={"start_page": 75})
    # Ein neues Lesen bringt wieder 69; die Korrektur bleibt.
    store_chapters(1, title, reading)
    by_number = {c["number"]: c for c in chapters_of(1, title)}
    assert (by_number["10"]["end_page"], by_number["11"]["start_page"], by_number["11"]["end_page"]) == (69, 70, 74)
    latin = sources.ledger(1)["subjects"][0]
    assert {m["label"]: m["pages"] for m in latin["missing"]} == {"Begleitband": [70, 71, 72, 73, 74]}
    assert client.patch("/api/accounts/1/materials/sources/chapters/99999", json={"start_page": 5}).status_code == 404


def test_the_transcription_model_is_chosen_per_purpose_and_set_by_parents(env, monkeypatch):
    from backend import ai_gateway as ai
    from backend.routers import mentor as mentor_routes
    client, state, _ = env
    client.app.include_router(mentor_routes.router, prefix="/api")
    for k, v in {'LEARNING_AI_MODEL': 'test', 'LEARNING_AI_URL': 'https://example.com/responses', 'LEARNING_AI_KEY': 'fake'}.items():
        monkeypatch.setenv(k, v)
    assert ai.model_for("sources") == "test" and ai.model_for("mentor") == "test"
    reply = client.put("/api/accounts/1/learning/mentor/budget-limits",
                       json={"monthly_eur": 80, "daily_eur": 12, "sources_model": "test-model"})
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert (body["limit_eur"], body["daily_limit_eur"], body["sources_model"]) == (80.0, 12.0, "test-model")
    # Abschreiben und Hintergrund nehmen das gewählte Modell, Üben bleibt beim Hauptmodell.
    assert ai.model_for("sources") == "test-model" and ai.model_for("background") == "test-model"
    assert ai.model_for("mentor") == "test" and ai.model_for("exam_scope") == "test"
    assert client.put("/api/accounts/1/learning/mentor/budget-limits", json={"sources_model": "gpt-9"}).status_code == 422
    # Zurück auf das Hauptmodell.
    assert client.put("/api/accounts/1/learning/mentor/budget-limits", json={"sources_model": ""}).json()["sources_model"] is None
    assert ai.model_for("sources") == "test"


def test_comparing_a_page_with_another_model_stores_nothing(env, monkeypatch):
    from backend import material_analysis as analysis
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")
    for k, v in {'LEARNING_AI_MODEL': 'test', 'LEARNING_AI_URL': 'https://example.com/responses', 'LEARNING_AI_KEY': 'fake'}.items():
        monkeypatch.setenv(k, v)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,source_label,source_page,printed_pages,file_bytes,mime_type,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','Seite 13','Substantive der a- und o-Deklination im Nominativ.','Begleitband',13,'[13]',?,'image/jpeg','ready','now','now')", (photo(),))
        material_id = c.execute("SELECT id FROM materials").fetchone()[0]
    seen = {}

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None, model=None):
        seen["model"] = model; seen["purpose"] = purpose
        return json.dumps({"kind": "book_page", "content_text": "Substantive der a- und o-Deklination im Nominativ", "printed_pages": [13],
                           "book_part": "Begleitband", "confidence": 0.9}), {}, "call-1"
    monkeypatch.setattr(analysis.ai, "complete", complete)
    reply = client.post(f"/api/accounts/1/materials/{material_id}/analysis/compare", json={"model": "test-model"})
    assert reply.status_code == 200, reply.text
    got = reply.json()
    assert seen == {"model": "test-model", "purpose": "sources"}
    assert got["pages_match"] and got["part_match"] and got["text_ratio"] > 0.95
    assert got["word_recall"] == 1.0 and got["word_precision"] == 1.0 and got["missing_words"] == []
    with closing(db.webapp_conn()) as c:
        row = c.execute("SELECT content_text,analysis_model FROM materials WHERE id=?", (material_id,)).fetchone()
    assert row[0].endswith(".") and row[1] is None, "die Eichung speichert nichts"
    assert client.post(f"/api/accounts/1/materials/{material_id}/analysis/compare", json={"model": "gpt-9"}).status_code == 422


def test_consent_buttons_are_not_books_and_the_dialog_is_reported():
    from backend import textbook_browser as tb
    for label in ("Abbrechen", "Weiter zur App", "Welche Daten werden übertragen?"):
        assert tb._CONSENT_PHRASES.fullmatch(label)
        assert tb._GENERIC_LABELS.fullmatch(label) or tb._GENERIC_PHRASES.search(label) or tb._CONSENT_PHRASES.fullmatch(label)
    assert not tb._CONSENT_PHRASES.fullmatch("Pontes Gesamtband")


def test_a_shelf_entry_that_is_no_book_can_be_removed(env):
    from backend.routers import textbooks as textbook_routes
    client, state, _ = env
    client.app.include_router(textbook_routes.router, prefix="/api")
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_credentials(account_id,portal_url,username,password_ciphertext,verification_status,updated_at,created_at) "
                  "VALUES(1,'https://schule.example','kind','x','catalog_ready','now','now')")
        for title in ("Abbrechen", "Weiter zur App", "Pontes"):
            c.execute("INSERT INTO digital_textbook_catalog(account_id,title,discovered_at) VALUES(1,?,'now')", (title,))
    books = client.get("/api/accounts/1/textbooks/catalog").json()["books"]
    bogus = [b for b in books if b["title"] != "Pontes"]
    for b in bogus:
        assert client.delete(f"/api/accounts/1/textbooks/catalog/{b['id']}").status_code == 204
    assert [b["title"] for b in client.get("/api/accounts/1/textbooks/catalog").json()["books"]] == ["Pontes"]
    assert client.delete("/api/accounts/1/textbooks/catalog/99999").status_code == 404


def test_a_second_photo_of_the_same_page_is_reported_and_blur_is_measured(env):
    from backend import materials as store
    from PIL import Image, ImageDraw, ImageFilter
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix="/api")

    def page(blur=0):
        img = Image.new("RGB", (900, 1200), (250, 250, 250))
        draw = ImageDraw.Draw(img)
        for y in range(60, 1150, 28):
            draw.text((40, y), "Servus clamat. Servi clamant. Lektion 1 Grammatik " * 2, fill=(20, 20, 20))
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        out = io.BytesIO(); img.save(out, "JPEG", quality=90); return out.getvalue()

    first = client.post("/api/accounts/1/materials", files={"file": ("a.jpg", page(), "image/jpeg")}, data={"subject_name": "LATEIN"}).json()
    assert first["duplicate_of"] is None and first["blurry"] is False
    second = client.post("/api/accounts/1/materials", files={"file": ("b.jpg", page(), "image/jpeg")}, data={"subject_name": "LATEIN"}).json()
    assert second["duplicate_of"]["id"] == first["id"], "dieselbe Seite noch einmal"
    soft = client.post("/api/accounts/1/materials", files={"file": ("c.jpg", page(blur=4), "image/jpeg")}, data={"subject_name": "LATEIN"}).json()
    assert soft["blurry"] is True
    with closing(db.webapp_conn()) as c:
        rows = {r[0]: (r[1], r[2]) for r in c.execute("SELECT id,phash,sharpness FROM materials")}
    assert rows[first["id"]][0] == rows[second["id"]][0] and rows[first["id"]][1] > store.BLURRY_BELOW > rows[soft["id"]][1]


def test_the_exam_card_says_why_a_place_is_still_pending(env):
    """Ein Foto liegt da, aber das Lesen scheiterte: kein „unterwegs", sondern der Grund."""
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")],
            homework=[(1, "LA", "BB S. 13 lernen", "2026-09-07")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,analysis_state,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','BB S. 13','Begleitband',13,'failed','now','now')")
    sources._SYNCED.clear()
    got = sources.exam_sources(1, "LATEIN", "2026-08-01", "2026-09-30")
    assert got["pending"] == 1 and got["ready"] == 0
    assert got["pending_items"][0]["kind"] == "failed" and got["pending_items"][0]["label"] == "Begleitband" and got["pending_items"][0]["page"] == 13
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE materials SET analysis_state='pending'")
    sources._SYNCED.clear()
    assert sources.exam_sources(1, "LATEIN", "2026-08-01", "2026-09-30")["pending_items"][0]["kind"] == "unread"


def test_a_budget_stop_is_named_as_such_on_the_exam_card(env):
    history(lessons=[(1, "2026-09-11", "LATEIN", LA, "Lektion 1")],
            homework=[(1, "LA", "BB S. 13 lernen", "2026-09-07")])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,source_label,source_page,analysis_state,analysis_error,created_at,updated_at) "
                  "VALUES(1,'book_page','LATEIN','BB S. 13','Begleitband',13,'failed','429','now','now')")
    sources._SYNCED.clear()
    got = sources.exam_sources(1, "LATEIN", "2026-08-01", "2026-09-30")
    assert got["pending_items"][0]["kind"] == "budget" and got["pending_items"][0]["error"] == "429"
