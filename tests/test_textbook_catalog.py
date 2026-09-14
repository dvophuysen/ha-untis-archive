from backend.textbook_browser import select_book_titles
from backend.textbook_catalog import infer_subject


def test_shelf_titles_are_filtered_and_nested_duplicates_removed():
    titles = select_book_titles([
        "Menü", "BiBox Mathematik Neue Wege 8", "BiBox Mathematik Neue Wege 8 Gymnasium G9 Niedersachsen",
        "Green Line 4 G9", "Abmelden",
    ])
    assert "BiBox Mathematik Neue Wege 8" in titles
    assert "Green Line 4 G9" in titles
    assert not any("Gymnasium" in title for title in titles)


def test_subject_inference_for_real_shelf_titles():
    assert infer_subject("BiBox Mathematik Neue Wege 8") == "mathematik"
    assert infer_subject("Universum Physik Sek I Niedersachsen") == "physik"
    assert infer_subject("Politik & Co. 7/8") == "politik"
    assert infer_subject("Unbekanntes Werk") is None
