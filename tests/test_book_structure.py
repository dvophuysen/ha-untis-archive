"""Die Buchstruktur: Inhaltsverzeichnis lesen, Kapitelregel, Klausurstoff."""
import json
from contextlib import closing

from test_learning import env  # noqa: F401
from test_sources import history, SN
from test_source_collector import shelf, fake_capture, png
from backend import ai_gateway as ai, book_structure as bs, db, source_collector as collector, sources, textbook_context as ctx
from backend.book_structure import Chapter


def chapters_fixture(account_id=1, title="¡Apúntate! 2"):
    return bs.store_chapters(account_id, title, [
        Chapter(number="Unidad 2", title="Mi barrio", start_page=30, level=1),
        Chapter(number="Unidad 3", title="¡Acércate!", start_page=48, level=1),
        Chapter(number="3A", title="Gramática", start_page=52, level=2),
        Chapter(number="3B", title="Resumen", start_page=60, level=2),
        Chapter(number="Unidad 4", title="De viaje", start_page=62, level=1),
        Chapter(number="", title="Vocabulario Unidad 2", start_page=165, kind="vocab", belongs_to="Unidad 2"),
        Chapter(number="", title="Vocabulario Unidad 3", start_page=171, kind="vocab", belongs_to="3"),
        Chapter(number="", title="Vocabulario Unidad 4", start_page=176, kind="vocab", belongs_to="Unidad 4"),
        Chapter(number="", title="Register", start_page=190, kind="appendix"),
    ])


def test_a_chapter_ends_where_the_next_one_begins(env):
    shelf()
    assert chapters_fixture() == 9
    rows = {(r["number"], r["title"]): (r["start_page"], r["end_page"]) for r in bs.chapters_of(1, "¡Apúntate! 2")}
    assert rows[("Unidad 3", "¡Acércate!")] == (48, 61), "die Einheit endet, wo Unidad 4 beginnt"
    assert rows[("3A", "Gramática")] == (52, 59) and rows[("3B", "Resumen")] == (60, 61)
    assert rows[("", "Vocabulario Unidad 3")] == (171, 175)
    assert rows[("Unidad 4", "De viaje")] == (62, 121), "das letzte Kapitel endet vor dem Anhang, gedeckelt auf sechzig Seiten"
    chapters = bs.chapters_of(1, "¡Apúntate! 2")
    assert bs.chapter_of(chapters, 55)["title"] == "Gramática", "der kleinste Abschnitt, der die Seite enthält"
    assert bs.chapter_of(chapters, 49)["title"] == "¡Acércate!"
    assert bs.chapter_of(chapters, 172) is None, "ein Anhang ist kein Stoffkapitel"
    unidad3 = next(c for c in chapters if c["title"] == "¡Acércate!")
    assert [c["title"] for c in bs.companions(chapters, unidad3)] == ["Vocabulario Unidad 3"]


def test_a_touched_chapter_is_collected_whole_with_its_vocabulary(env):
    """Eine Seite aus Unidad 3 im Unterricht: die ganze Einheit und ihr Vokabelteil
    werden zu holende Stellen, die genannte Seite kommt zuerst."""
    history(homework=[(1, 'SN', '#libro, p. 50 vocabulario 4 b', '2026-09-10')])
    shelf()
    chapters_fixture()
    result = sources.sync_links(1)
    assert result["links"] == 1 + 14 + 5, "die Stelle, Seiten 48–61 und der Vokabelteil 171–175"
    book = sources.ledger(1)
    only = book["subjects"][0]
    assert only["pending"] == 19 and only["pending_pages"][:3] == [48, 49, 50]
    assert only["chapters"][0]["title"] == "¡Acércate!" and only["chapters"][0]["pages"] == 14
    assert only["chapters"][0]["companions"][0]["title"] == "Vocabulario Unidad 3"
    groups = collector.wanted_pages(1)
    assert sorted(groups[0]["pages"])[:2] == [48, 49]
    with closing(db.webapp_conn()) as conn:
        order = [r[0] for r in conn.execute(
            "SELECT page FROM source_links WHERE account_id=1 AND status='pending' GROUP BY page "
            "ORDER BY MIN(entry_kind='chapter'), MAX(entry_date) DESC, page")]
    assert order[0] == 50, "die im Unterricht genannte Seite vor den Kapitelseiten"
    # Wird der Eintrag geändert und nennt kein Kapitel mehr, verschwinden die Kapitelseiten.
    import sqlite3
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("UPDATE homework SET text='Vokabeln wiederholen' WHERE id=1")
    sources.sync_links(1)
    with closing(db.webapp_conn()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM source_links").fetchone()[0] == 0


async def test_the_table_of_contents_is_read_once_from_the_first_pages(env, monkeypatch):
    shelf()
    capture, calls = fake_capture({2, 3, 4, 5, 6, 7, 8, 9})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) VALUES(1,'2026/27',8,1,1,'now')")
    answers = [
        {"is_toc": True, "continues": True, "chapters": [
            {"number": "Unidad 1", "title": "Hola", "start_page": 8, "level": 1},
            {"number": "Unidad 2", "title": "Mi barrio", "start_page": 30, "level": 1}]},
        {"is_toc": True, "continues": False, "chapters": [
            {"number": "Unidad 3", "title": "¡Acércate!", "start_page": 48, "level": 1},
            {"number": "", "title": "Vocabulario", "start_page": 160, "kind": "vocab"}]},
    ]
    seen = []

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
        seen.append((purpose, len(images or [])))
        return json.dumps(answers.pop(0)), 0, 0
    monkeypatch.setattr(bs.ai, "complete", complete)
    book, credentials = ctx.book_and_credentials(1, book_id=None, subject="spanisch")
    outcome = await bs.read_toc(1, book, credentials)
    assert outcome["state"] == "ready" and outcome["chapters"] == 4 and outcome["pages"] == [2, 3, 4, 5, 6, 7, 8, 9]
    assert calls == [[2, 3, 4, 5], [6, 7, 8, 9]], "weitergeblättert, weil das Verzeichnis weiterging"
    assert seen == [("sources", 2), ("sources", 2)], "zwei Doppelseitenbilder je Aufruf, aus dem Quellen-Rahmen"
    assert bs.toc_state(1, book["title"]) == "ready"
    rows = {r["title"]: (r["start_page"], r["end_page"]) for r in bs.chapters_of(1, book["title"])}
    assert rows["Mi barrio"] == (30, 47) and rows["¡Acércate!"] == (48, 107), "das letzte Kapitel endet vor dem Anhang, aber höchstens 60 Seiten"


async def test_a_run_reads_the_table_of_contents_before_fetching_pages(env, monkeypatch):
    history(homework=[(1, 'SN', 'libro p. 50', '2026-09-10')])
    shelf()
    capture, calls = fake_capture(set(range(2, 10)) | set(range(48, 62)) | {171, 172, 173, 174, 175})
    monkeypatch.setattr(ctx, "capture_pages", capture)
    with closing(db.webapp_conn()) as conn:
        conn.execute("INSERT OR IGNORE INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) VALUES(1,'2026/27',8,1,1,'now')")
        conn.execute("UPDATE digital_textbook_access SET toc_state=NULL")

    async def complete(account_id, purpose, instruction, context, images=None, max_output=4096, session_id=None):
        if "Inhaltsverzeichnis" in instruction:
            return json.dumps({"is_toc": True, "continues": False, "chapters": [
                {"number": "Unidad 3", "title": "¡Acércate!", "start_page": 48, "level": 1},
                {"number": "Unidad 4", "title": "De viaje", "start_page": 62, "level": 1},
                {"number": "", "title": "Vocabulario Unidad 3", "start_page": 171, "kind": "vocab", "belongs_to": "Unidad 3"},
                {"number": "", "title": "Vocabulario Unidad 4", "start_page": 176, "kind": "vocab", "belongs_to": "Unidad 4"}]}), 0, 0
        page = context["hinweise"]["buchseite"]["bestellte_seite"]
        return json.dumps({"kind": "book_page", "content_text": "Text", "printed_pages": [page, page + 1], "fits_quote": "ja", "confidence": 0.9}), 0, 0
    monkeypatch.setattr(bs.ai, "complete", complete)
    monkeypatch.setattr(collector.analysis.ai, "complete", complete)
    summary = await collector.collect(1, budget=5)
    assert summary["toc"] == {"¡Apúntate! 2": "ready"}
    assert calls[0] == [2, 3, 4, 5], "erst das Verzeichnis"
    assert calls[1] == [50], "das knappe Budget geht an die im Unterricht genannte Seite"
    summary = await collector.collect(1, budget=30)
    assert set(calls[2]) == (set(range(48, 62)) | set(range(171, 176))) - {50} and calls[2] == sorted(calls[2]), \
        "dann die Einheit und ihr Vokabelteil, in Buchreihenfolge geblättert"
    assert summary["stored"] == 18 and summary["verified"] == 18
    book = sources.ledger(1)["subjects"][0]
    assert book["chapters"][0]["pages_stored"] == 14 and book["pending"] == 0


def test_exam_scope_lists_the_chapters_touched_in_the_period(env):
    history(homework=[(1, 'SN', 'libro p. 50', '2026-09-10'), (2, 'SN', 'libro p. 63', '2026-08-20')])
    shelf()
    chapters_fixture()
    sources.sync_links(1)
    from backend.exam_scope import book_chapters
    found = book_chapters(1, "SPANISCH", "2026-09-01", "2026-09-30")
    assert [c["title"] for c in found] == ["¡Acércate!"], "Unidad 4 wurde vor dem Zeitraum angeschnitten"
    assert found[0]["cited_pages"] == [50] and found[0]["companions"][0]["start_page"] == 171


def test_the_source_stock_has_its_own_monthly_budget(env, monkeypatch):
    from fastapi import HTTPException
    import pytest
    monkeypatch.setenv("LEARNING_AI_MODEL", "test-model")
    with closing(db.webapp_conn()) as c:
        ai.init_config(c)
        c.execute("UPDATE mentor_ai_config SET sources_micro=1000000 WHERE id=1")
    key = ai.reserve(1, "sources", None, 1000, 1000)
    ai.settle(key, {"usage": {"prompt_tokens": 100, "completion_tokens": 100}})
    with pytest.raises(HTTPException) as caught:
        ai.reserve(1, "sources", None, 1000, 30000)
    assert caught.value.status_code == 429 and "Quellenbestand" in caught.value.detail
    assert ai.reserve(1, "background", None, 1000, 1000), "der Hintergrund-Rahmen bleibt davon unberührt"
    status = ai.status()
    assert status["sources_limit_eur"] == 1.0 and status["sources_eur"] > 0
