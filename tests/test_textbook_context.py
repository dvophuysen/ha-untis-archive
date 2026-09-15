from backend.textbook_context import page_numbers

def test_page_numbers_expand_ranges_and_keep_later_task_page():
    assert page_numbers("Buch, S.30-32. Lest M6. Bearbeitet Aufgabe 1 auf S. 34") == [30,31,32,34]

def test_page_numbers_are_bounded():
    assert page_numbers("Seite 10-99") == []

def test_page_numbers_read_every_spelling_but_only_book_pages():
    # Spanisch schreibt „p.", Latein trennt Textband und Arbeitsheft.
    assert page_numbers("#libro, p. 50   vocabulario    4 b") == [50]
    assert page_numbers("Wortschatztraining (TB S. 13 Aufg. C, AH S. 7 Aufg. C und Z)") == [13]
    assert page_numbers("Arbeitsheft S. 85, Aufg. 5") == []
