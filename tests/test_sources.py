"""Die Quellenbilanz: was der Unterricht nennt und was davon fehlt.

Die Beispieltexte stammen wörtlich aus dem Untis-Bestand beider Kinder.
"""
import sqlite3
from contextlib import closing

from test_learning import env, child
from backend import db, sources
from backend.routers import materials as materials_routes

LESSONS = ("id INTEGER PRIMARY KEY, account_id INTEGER, date TEXT, subject_name TEXT, "
           "subject_untis_id INTEGER, teacher_untis_id INTEGER, code TEXT, lstext TEXT, "
           "lstext_manual_override TEXT, payload_json TEXT, is_supervision_guess INTEGER, "
           "supervision_manual_override INTEGER")
# Hausaufgaben führen in Untis kein subject_untis_id — nur das Kürzel.
HOMEWORK = ("id INTEGER PRIMARY KEY, account_id INTEGER, subject_name TEXT, text TEXT, assigned_date TEXT")


def payload(short):
    return '{"su": [{"name": "%s"}]}' % short


LA, SN = payload('LA'), payload('SN')


def history(lessons=(), homework=()):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f'CREATE TABLE IF NOT EXISTS lessons({LESSONS})')
        c.execute(f'CREATE TABLE IF NOT EXISTS homework({HOMEWORK})')
        c.executemany('INSERT INTO lessons(id,account_id,date,subject_name,payload_json,code,lstext) '
                      'VALUES(?,1,?,?,?,NULL,?)', lessons)
        c.executemany('INSERT INTO homework(id,account_id,subject_name,text,assigned_date) '
                      'VALUES(?,1,?,?,?)', homework)


def test_only_an_explicit_page_marker_counts_as_a_page():
    # „vocabulario 4 b" ist die Aufgabe, nicht Seite 4.
    got = sources.citations('#libro, p. 50   vocabulario    4 b     (preparar un mapa mental)')
    assert [(c['label'], c['pages']) for c in got] == [('Schulbuch', [50])]
    # Ein Wort, das zufällig „AH" enthält, ist keine Quelle.
    assert sources.citations('Klassenfahrt 8D nach Oldenburg') == []
    assert sources.citations('Übungen zur 3. Person Präsens') == []


def test_each_page_keeps_the_book_part_it_was_named_with():
    # „TB" ist nur in Latein der Textband; im Englischen ist es das Text Book,
    # also das Schulbuch. Ohne Fach gilt die allgemeine Lesart (D114).
    latein = ('Wortschatztraining Lektion 1, Übungen zu debere und Infinitiven '
              '(TB S. 13 Aufg. C, AH S. 7 Aufg. C und Z)')
    got = sources.citations(latein, 'LATEIN')
    assert [(c['label'], c['pages']) for c in got] == [('Textband', [13]), ('Arbeitsheft', [7])]
    assert sources.citations(latein, 'ENGLISCH')[0]['label'] == 'Schulbuch'
    assert sources.citations('Vocabulary TB p. 24', 'ENGLISCH')[0]['label'] == 'Schulbuch'
    assert sources.citations('Substantive BB S. 73', 'LATEIN')[0]['label'] == 'Begleitband'
    assert sources.citations('Substantive BB S. 73', 'ENGLISCH')[0]['label'] == 'Unbekannte Quelle'
    # Der zuletzt genannte Teil gilt weiter, auch über einen Satz hinweg.
    got = sources.citations('Buch, S.30-32. lest M6 und den Infokasten. Bearbeitet Aufgabe 1 auf S. 34')
    assert [(c['label'], c['pages']) for c in got] == [('Schulbuch', [30, 31, 32]), ('Schulbuch', [34])]
    # Steht nirgends ein Buchteil, wird keiner erfunden.
    assert sources.citations('12 irregular verbs (chart p. 206 - drive/drove)')[0]['label'] == 'Unbekannte Quelle'


def test_pages_are_listed_readably():
    assert sources.page_list([6, 7, 8, 12]) == 'S. 6–8 und 12'
    assert sources.page_list([19]) == 'S. 19'
    assert sources.page_list([28, 26, 27]) == 'S. 26–28'


def test_the_ledger_joins_the_short_subject_of_a_homework_to_its_lessons(env):
    # Das Kürzel steht nur im payload_json der Stunde; ohne diesen Weg stünde
    # Latein zweimal auf der Liste, als „LATEIN" und als „LA".
    history(lessons=[(1, '2026-09-11', 'LATEIN', LA, 'Übungen (TB S. 19 Aufg. A2)')],
            homework=[(1, 'LA', 'Textband Seite 15, Arbeitsheft S. 7 Aufg. C', '2026-09-07')])
    book = sources.ledger(1)
    assert [s['subject'] for s in book['subjects']] == ['LATEIN'], 'Kürzel und Langform sind dasselbe Fach'
    missing = {m['label']: m['pages'] for m in book['subjects'][0]['missing']}
    assert missing == {'Textband': [15, 19], 'Arbeitsheft': [7]}
    assert book['missing_total'] == 3


def test_a_digital_book_page_is_fetched_not_asked_for_but_the_workbook_is(env):
    history(lessons=[(1, '2026-09-11', 'SPANISCH', SN, 'Repaso (#libro, p. 50 und #cda, p. 28)')])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'spanisch','¡Apúntate! 2','now')")
    only = sources.ledger(1)['subjects'][0]
    # Ein Treffer im Katalog ist kein Zugriff (D31): die Seite ist unterwegs, nicht vorhanden.
    assert only['digital'] == 0 and only['pending'] == 1 and only['pending_pages'] == [50] and only['has_book']
    assert [(m['label'], m['pages']) for m in only['missing']] == [('Arbeitsheft', [28])]
    # Liegt die Seite abgerufen im Bestand, zählt sie als digital vorhanden.
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,page_check,"
                  "fits_quote,analysis_state,created_at,updated_at) VALUES(1,'book_page','SPANISCH','Apúntate S. 50',"
                  "'book_fetch','¡Apúntate! 2',50,'ok','ja','ready','now','now')")
    only = sources.ledger(1)['subjects'][0]
    assert only['digital'] == 1 and only['pending'] == 0
    with closing(db.webapp_conn()) as c:
        link = c.execute("SELECT status,detail,material_id FROM source_links WHERE account_id=1 AND page=50").fetchone()
    assert (link[0], link[1]) == ('digital', 'belegt') and link[2] is not None


def test_a_book_that_delivers_nothing_puts_its_pages_on_the_list(env):
    history(lessons=[(9, '2026-09-01', 'SPANISCH', SN, '')], homework=[(1, 'SN', 'libro p. 18', '2026-09-10')])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'spanisch','¡Apúntate! 2','now')")
        c.execute("INSERT INTO digital_textbook_access(account_id,book_title,status,checked_at) VALUES(1,'¡Apúntate! 2','blank','now')")
    assert sources.ledger(1)['subjects'][0]['pending'] == 1, 'erst nach vergeblichen Versuchen gilt sie als nicht lieferbar'
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE source_links SET attempts=2 WHERE account_id=1")
    only = sources.ledger(1)['subjects'][0]
    assert only['pending'] == 0 and only['missing'][0]['reason'] == 'unavailable'


def test_an_unknown_source_whose_book_page_does_not_fit_is_another_booklet(env):
    history(lessons=[(9, '2026-09-01', 'SPANISCH', SN, '')], homework=[(1, 'SN', 'S. 64/5 zu Ende notieren', '2026-09-10')])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'spanisch','¡Apúntate! 2','now')")
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,origin,source_book,source_page,page_check,"
                  "fits_quote,analysis_state,created_at,updated_at) VALUES(1,'book_page','SPANISCH','S. 64',"
                  "'book_fetch','¡Apúntate! 2',64,'ok','nein','ready','now','now')")
    only = sources.ledger(1)['subjects'][0]
    assert only['digital'] == 0 and only['missing'][0]['reason'] == 'passt_nicht'


def test_links_follow_the_untis_entries(env):
    history(homework=[(1, 'LA', 'TB S. 13 Aufg. C', '2026-09-07')])
    assert sources.sync_links(1)['links'] == 1
    with closing(db.webapp_conn()) as c:
        row = c.execute("SELECT entry_kind,entry_id,subject_name,part_kind,page,quote FROM source_links").fetchone()
    assert tuple(row) == ('homework', 1, 'LA', 'book', 13, 'TB S. 13 Aufg. C')
    # Der Eintrag wird in Untis geändert: die alte Stelle verschwindet, die neue kommt.
    import sqlite3
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("UPDATE homework SET text='TB S. 14 Aufg. D' WHERE id=1")
    result = sources.sync_links(1)
    assert result['links'] == 1 and result['removed'] == 1
    with closing(db.webapp_conn()) as c:
        assert [r[0] for r in c.execute("SELECT page FROM source_links")] == [14]


def test_a_scanned_page_disappears_from_the_list(env):
    history(homework=[(1, 'LA', 'Arbeitsheft S. 7 Aufg. C und Z', '2026-09-07')])
    assert sources.ledger(1)['missing_total'] == 1
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,created_at,updated_at) "
                  "VALUES(1,'workbook','LA','Arbeitsheft S. 7','Aufgabe C …','now','now')")
    assert sources.ledger(1)['missing_total'] == 0


def test_the_list_is_readable_for_a_child_and_survives_an_empty_archive(env):
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix='/api')
    history(homework=[(1, 'LA', 'Textband Seite 19, für die Klassenarbeit lernen', '2026-09-14')])
    child(state)
    body = client.get('/api/accounts/1/materials/sources').json()
    assert body['subjects'][0]['missing'][0]['pages_label'] == 'S. 19'
    assert 'Klassenarbeit' in body['subjects'][0]['missing'][0]['quote']
    assert client.get('/api/accounts/2/materials/sources').status_code == 403


def test_the_same_page_under_two_names_is_one_place():
    """Ein Eintrag schreibt „Buch S. 48", ein anderer „Schulbuch S. 48". Das ist
    eine Seite. Nebeneinander galt sie gleichzeitig als da und als fehlend, weil
    eine vorliegende Seite nur die erste passende Stelle belegt (D99)."""
    from backend.lernstand import merge_places, places_label
    stellen = [{"label": None, "pages": [48]}, {"label": "Schulbuch", "pages": [48]},
               {"label": "Arbeitsheft", "pages": [26]}]
    assert merge_places(stellen) == [{"label": "Schulbuch", "pages": [48]},
                                     {"label": "Arbeitsheft", "pages": [26]}]
    assert places_label(stellen) == "Schulbuch S. 48 · Arbeitsheft S. 26"
    # Verschiedene Bücher mit derselben Seitenzahl bleiben getrennt.
    zwei = [{"label": "Schulbuch", "pages": [26]}, {"label": "Arbeitsheft", "pages": [26]}]
    assert merge_places(zwei) == zwei
    # Der Begleitband ist ein eigenes Buch und wird nie mit dem Schulbuch verschmolzen.
    eigen = [{"label": "Schulbuch", "pages": [10]}, {"label": "Begleitband", "pages": [10]}]
    assert merge_places(eigen) == eigen
    # Seiten derselben Nennung werden vereinigt, nicht verdoppelt.
    assert merge_places([{"label": "Buch", "pages": [48]}, {"label": None, "pages": [49]}]) \
        == [{"label": "Buch", "pages": [48, 49]}]


def test_the_same_short_form_means_different_books_in_different_subjects():
    """Bei Kind B stand in Englisch „Textband", weil „TB" wie in Latein gelesen
    wurde. „TB" ist im Englischen das Text Book, also das Schulbuch; nur Latein
    hat einen Textband und einen Begleitband (D114)."""
    for subject in ('ENGLISCH', 'Englisch', 'SPANISCH', 'MATHEMATIK', ''):
        assert sources.part_of('TB S. 24', subject) == ('Schulbuch', 'book'), subject
    for subject in ('LATEIN', 'Latein bilingual', 'LA', 'la'):
        assert sources.part_of('TB S. 24', subject) == ('Textband', 'book'), subject
        assert sources.part_of('BB S. 24', subject) == ('Begleitband', 'book'), subject
    # Ein Kürzel wird genau verglichen, nie als Teilwort.
    assert sources.part_of('TB S. 24', 'Klassenlehrerstunde') == ('Schulbuch', 'book')
    # Ausgeschrieben bleibt es in jedem Fach eindeutig.
    assert sources.part_of('Textband S. 24', 'ENGLISCH') == ('Textband', 'book')


def test_the_english_short_forms_split_a_homework_into_its_three_sources():
    """Bei Kind B stand in Englisch eine Hausaufgabe als eine einzige, dazu noch
    unbekannte Quelle in der Liste. „WB" ist das Workbook, also das Arbeitsheft,
    „Voc." der Vokabelteil im Anhang des Schulbuchs, und „pp. 216/7" sind die
    Seiten 216 und 217 — die zweite Zahl ist die abgekürzte Folgeseite (D117)."""
    text = ('Voc. pp. 216/7 (Copy and learn.) Irregular verbs TB p. 206 '
            '(Copy to end of page) Zusatz: WB p. 6, ex. 6')
    assert [(c['label'], c['pages']) for c in sources.citations(text, 'ENGLISCH')] == [
        ('Schulbuch, Vokabelteil', [216, 217]), ('Schulbuch', [206]), ('Arbeitsheft', [6])]
    # Das Arbeitsheft heißt in jedem Fach so.
    assert sources.part_of('WB p. 4, ex. 2', 'ENGLISCH') == ('Arbeitsheft', 'workbook')
    assert sources.part_of('WB S. 4', 'LATEIN') == ('Arbeitsheft', 'workbook')
    # Der Wortschatz steht in den modernen Fremdsprachen im Schulbuch. In Latein
    # wäre es der Begleitband, ein eigenes Buch: dort lieber unbestimmt bleiben,
    # als die falsche Seite zu belegen.
    assert sources.part_of('Voc. p. 213', 'SPANISCH') == ('Schulbuch, Vokabelteil', 'book')
    assert sources.part_of('Voc. S. 213', 'LATEIN') == ('', '')


def test_an_abbreviated_follow_on_page_only_counts_after_the_plural_marker():
    """«pp.» steht für zwei Seiten, «p.» für eine. Hinter „S. 60/1" und
    „p. 48/5" steht darum die Aufgabe, nicht die nächste Seite (D117)."""
    assert sources.page_hits('Voc. pp. 216/7') == [(5, 14, [216, 217])]
    assert [pages for _, _, pages in sources.page_hits('pp. 98/102')] == [[98, 99, 100, 101, 102]]
    for einzeln in ('S. 60/1', 'p. 48/5', 'Seite 60/1'):
        assert [pages for _, _, pages in sources.page_hits(einzeln)] == [[int(einzeln.split()[-1].split('/')[0])]]
    # Rückwärts oder weit weg ist keine Folgeseite, sondern etwas anderes.
    assert [pages for _, _, pages in sources.page_hits('pp. 216/5')] == [[216]]


def test_a_photo_can_take_a_page_of_an_unknown_source(env):
    """„S. 105“ ohne Buch heißt „Unbekannte Quelle“. Bis 1.13.31 lehnte der
    Server das Foto dazu als unbekannten Buchteil ab (422), und in der App
    passierte scheinbar nichts. Jetzt belegt es die Stelle."""
    import io
    from PIL import Image
    client, _, _ = env
    client.app.include_router(materials_routes.router, prefix='/api')
    history(homework=[(1, 'EN', '12 irregular verbs (chart p. 206 - drive/drove)', '2026-09-14')])
    need = sources.ledger(1)['subjects'][0]
    assert need['missing'][0]['label'] == 'Unbekannte Quelle'
    shot = io.BytesIO(); Image.new('RGB', (40, 30), (200, 200, 200)).save(shot, 'PNG')
    r = client.post('/api/accounts/1/materials', files={'file': ('seite.png', shot.getvalue(), 'image/png')},
                    data={'subject_name': need['subject'], 'source_label': 'Unbekannte Quelle', 'source_page': '206'})
    assert r.status_code == 200, r.text
    assert r.json()['source_label'] in (None, '') and r.json()['source_page'] == 206
    assert sources.ledger(1)['missing_total'] == 0
