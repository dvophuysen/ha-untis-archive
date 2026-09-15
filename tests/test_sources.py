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
           "lstext_manual_override TEXT, is_supervision_guess INTEGER, supervision_manual_override INTEGER")
HOMEWORK = ("id INTEGER PRIMARY KEY, account_id INTEGER, subject_name TEXT, subject_untis_id INTEGER, "
            "text TEXT, assigned_date TEXT")


def history(lessons=(), homework=()):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f'CREATE TABLE IF NOT EXISTS lessons({LESSONS})')
        c.execute(f'CREATE TABLE IF NOT EXISTS homework({HOMEWORK})')
        c.executemany('INSERT INTO lessons(id,account_id,date,subject_name,subject_untis_id,code,lstext) '
                      'VALUES(?,1,?,?,?,NULL,?)', lessons)
        c.executemany('INSERT INTO homework(id,account_id,subject_name,subject_untis_id,text,assigned_date) '
                      'VALUES(?,1,?,?,?,?)', homework)


def test_only_an_explicit_page_marker_counts_as_a_page():
    # „vocabulario 4 b" ist die Aufgabe, nicht Seite 4.
    got = sources.citations('#libro, p. 50   vocabulario    4 b     (preparar un mapa mental)')
    assert [(c['label'], c['pages']) for c in got] == [('Schulbuch', [50])]
    # Ein Wort, das zufällig „AH" enthält, ist keine Quelle.
    assert sources.citations('Klassenfahrt 8D nach Oldenburg') == []
    assert sources.citations('Übungen zur 3. Person Präsens') == []


def test_each_page_keeps_the_book_part_it_was_named_with():
    got = sources.citations('Wortschatztraining Lektion 1, Übungen zu debere und Infinitiven '
                            '(TB S. 13 Aufg. C, AH S. 7 Aufg. C und Z)')
    assert [(c['label'], c['pages']) for c in got] == [('Schulbuch', [13]), ('Arbeitsheft', [7])]
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
    history(lessons=[(1, '2026-09-11', 'LATEIN', 7, 'Übungen (TB S. 19 Aufg. A2)')],
            homework=[(1, 'LA', 7, 'Textband Seite 15, Arbeitsheft S. 7 Aufg. C', '2026-09-07')])
    book = sources.ledger(1)
    assert [s['subject'] for s in book['subjects']] == ['LATEIN'], 'Kürzel und Langform sind dasselbe Fach'
    missing = {m['label']: m['pages'] for m in book['subjects'][0]['missing']}
    assert missing == {'Schulbuch': [15, 19], 'Arbeitsheft': [7]}
    assert book['missing_total'] == 3


def test_a_digital_book_is_not_asked_for_but_the_workbook_is(env):
    history(lessons=[(1, '2026-09-11', 'SPANISCH', 9, 'Repaso (#libro, p. 50 und #cda, p. 28)')])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO digital_textbook_catalog(account_id,subject_name,title,discovered_at) VALUES(1,'spanisch','¡Apúntate! 2','now')")
    only = sources.ledger(1)['subjects'][0]
    assert only['digital'] == 1 and only['has_book']
    assert [(m['label'], m['pages']) for m in only['missing']] == [('Arbeitsheft', [28])]


def test_a_scanned_page_disappears_from_the_list(env):
    history(homework=[(1, 'LA', 7, 'Arbeitsheft S. 7 Aufg. C und Z', '2026-09-07')])
    assert sources.ledger(1)['missing_total'] == 1
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO materials(account_id,kind,subject_name,title,content_text,created_at,updated_at) "
                  "VALUES(1,'workbook','LA','Arbeitsheft S. 7','Aufgabe C …','now','now')")
    assert sources.ledger(1)['missing_total'] == 0


def test_the_list_is_readable_for_a_child_and_survives_an_empty_archive(env):
    client, state, _ = env
    client.app.include_router(materials_routes.router, prefix='/api')
    history(homework=[(1, 'LA', 7, 'Textband Seite 19, für die Klassenarbeit lernen', '2026-09-14')])
    child(state)
    body = client.get('/api/accounts/1/materials/sources').json()
    assert body['subjects'][0]['missing'][0]['pages_label'] == 'S. 19'
    assert 'Klassenarbeit' in body['subjects'][0]['missing'][0]['quote']
    assert client.get('/api/accounts/2/materials/sources').status_code == 403
