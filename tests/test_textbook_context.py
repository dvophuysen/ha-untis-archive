from backend.textbook_context import page_numbers

def test_page_numbers_expand_ranges_and_keep_later_task_page():
    assert page_numbers("Buch, S.30-32. Lest M6. Bearbeitet Aufgabe 1 auf S. 34") == [30,31,32,34]

def test_page_numbers_are_bounded():
    assert page_numbers("Seite 10-99") == []
