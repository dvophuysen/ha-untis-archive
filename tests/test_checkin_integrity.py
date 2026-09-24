"""Comments, comprehension and account-wide reminders must remain distinct."""
from contextlib import closing
from datetime import date, datetime, time
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from test_learning import env, child
from backend import db
from backend import family_board
from backend.learning import today_local
from backend.routers import checkins, dashboard, notify, today


def _gap(account_id, day):
    """Rückmeldelücke der Startseite, abends: alle Stunden des Tages sind vorbei."""
    got = family_board.feedback(account_id, day, datetime.combine(day, time(23, 59)))
    return {'unrated_lessons': got['earlier'] + got['today'], 'total_lessons': got['total']}


def install(env):
    client, state, patch = env
    client.app.include_router(checkins.router, prefix='/api')
    child(state)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('CREATE TABLE lessons(id INTEGER PRIMARY KEY, account_id INTEGER, untis_period_id INTEGER, subject_untis_id INTEGER, date TEXT, start_time INTEGER, end_time INTEGER, was_absent INTEGER, code TEXT, subject_name TEXT)')
        c.executemany('INSERT INTO lessons VALUES(?, ?, ?, 7, ?, 800, 900, 0, NULL, ?)',
                      [(i, 1 if i < 6 else 2, 100+i, date.today().isoformat(), 'Testfach') for i in range(1, 7)])
    return client, state, patch


def post(client, lesson, **body):
    return client.post(f'/api/accounts/1/lessons/{lesson}/checkin', json=body)


def test_comment_roundtrip_preserves_rating_and_account_boundary(env):
    client, state, _ = install(env)
    result = post(client, 1, note='Heft mitbringen')
    assert result.status_code == 200 and result.json()['rating'] is None
    assert post(client, 1, rating=3, note='verstanden').json()['rating'] == 3
    # A comment-only save must not overwrite a rating from another client.
    assert post(client, 1, rating=None, note='Neue Notiz').json()['rating'] == 3
    assert post(client, 1, rating=4, note='Aufsicht').json()['rating'] == 4
    assert post(client, 6, note='wrong account').status_code == 404
    assert post(client, 1, rating=0).status_code == 422
    assert post(client, 1, rating=5).status_code == 422
    with closing(db.webapp_conn()) as c:
        row = dict(c.execute('SELECT * FROM lesson_checkins WHERE lesson_id=1').fetchone())
        assert row['untis_period_id'] == 101 and row['rating'] == 4
        assert c.execute('SELECT COUNT(*) FROM lesson_checkins').fetchone()[0] == 1
    db.init_webapp_db()
    with closing(db.webapp_conn()) as c:
        assert dict(c.execute('SELECT * FROM lesson_checkins WHERE lesson_id=1').fetchone()) == row


def test_comprehension_ignores_comments_and_supervision_but_gaps_do_not(env):
    client, _, patch = install(env)
    post(client, 1, note='Material')
    post(client, 2, rating=4)
    post(client, 3, rating=1)
    post(client, 4, rating=3)
    assert dashboard._comprehension_for_subjects(1, {7}) == {7: {'hard': 1, 'total': 2}}
    assert dashboard._comprehension_for_subjects(2, {7}) == {7: {'hard': 0, 'total': 0}}
    assert _gap(1, date.today()) == {'unrated_lessons': 2, 'total_lessons': 5}
    patch.setattr(today, 'lessons_for_date', lambda c, a, d: [dict(id=i, is_cancelled=False, was_absent=False) for i in range(1,6)] if d == today_local().isoformat() else [])
    patch.setattr(today, 'upcoming_exams', lambda *a, **kw: [])
    patch.setattr(today, 'hidden_keys', lambda a: set())
    patch.setattr(today, 'lesson_is_hidden', lambda *a: False)
    import asyncio
    data=asyncio.run(today.today(1, env[1].user))
    assert data['summary']['unrated_lessons'] == 2
    assert data['lessons'][0]['checkin']['note'] == 'Material'


def test_reminder_counts_account_once_even_without_linked_users(env):
    client, _, patch = install(env)
    post(client, 1, note='Material')
    post(client, 2, rating=4)
    post(client, 3, rating=3)
    patch.setattr(notify, '_now_hhmm', lambda: 1700)
    patch.setattr(notify, 'upcoming_exams', lambda *a, **kw: [])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO account_settings(account_id,notify_token,created_at,updated_at) VALUES(1,'test-token','now','now')")
    result=notify.notify_summary(1, 'test-token')
    assert len(result['users']) == 3
    assert result['unrated_lessons_today'] == 3
    assert 'noch 3 Stunden' in result['suggested_messages']['checkin_reminder']
    with closing(db.webapp_conn()) as c:
        c.execute('DELETE FROM user_account_links WHERE account_id=1')
    result=notify.notify_summary(1, 'test-token')
    assert result['users'] == [] and result['unrated_lessons_today'] == 3
    assert 'noch 3 Stunden' in result['suggested_messages']['checkin_reminder']


def test_upgrade_preserves_all_rows_ids_and_is_idempotent(env):
    client, _, _ = install(env)
    # Reconstruct the pre-upgrade constraint, then exercise the real migration.
    with closing(db.webapp_conn()) as c:
        c.executescript('''
        DELETE FROM schema_meta WHERE key='migration:checkins_030_optional_rating';
        DROP TABLE lesson_checkins;
        CREATE TABLE lesson_checkins(
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL,
          lesson_id INTEGER NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id),
          rating INTEGER NOT NULL, note TEXT, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, untis_period_id INTEGER,
          UNIQUE(account_id,lesson_id));
        INSERT INTO lesson_checkins VALUES(42,1,1,2,2,'Existing note','before','before',101);
        INSERT INTO lesson_checkins VALUES(43,2,6,3,4,'Supervision','before','before',106);
        ''')
        before=[tuple(r) for r in c.execute('SELECT * FROM lesson_checkins ORDER BY id')]
    db.init_webapp_db()
    db.init_webapp_db()
    with closing(db.webapp_conn()) as c:
        assert [tuple(r) for r in c.execute('SELECT * FROM lesson_checkins ORDER BY id')] == before
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []
    assert post(client, 2, note='Only a note').json()['rating'] is None


def test_hidden_courses_do_not_count_as_open_feedback(env):
    # Französisch und Religion des Kindes sind ausgeblendet, weil es sie nicht
    # besucht. Sie standen trotzdem als „zwei Rückmeldungen offen" auf dem
    # Dashboard, ohne im Stundenplan zu erscheinen.
    client, _, _ = install(env)
    from backend.courses import course_key
    assert _gap(1, date.today())['total_lessons'] == 5
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO hidden_courses(account_id,course_key,created_at) VALUES(1,?,'now')",
                  (course_key(7, None, 'Testfach', None),))
    assert _gap(1, date.today()) == {'unrated_lessons': 0, 'total_lessons': 0}
