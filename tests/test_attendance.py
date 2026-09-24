"""Explicit Untis lateness must never become absence or block feedback."""
import sqlite3
from datetime import date, datetime, time
from threading import RLock
from contextlib import closing

import pytest

from test_learning import env
from test_checkin_integrity import install, post
from test_storage_concurrent import UntisStorage
from backend import db, family_board


def _gap(account_id, day):
    """Rückmeldelücke der Startseite, abends: alle Stunden des Tages sind vorbei."""
    got = family_board.feedback(account_id, day, datetime.combine(day, time(23, 59)))
    return {'unrated_lessons': got['earlier'] + got['today'], 'total_lessons': got['total']}


def seed(env):
    client, state, patch = install(env)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.executescript('''
        ALTER TABLE lessons ADD COLUMN absence_reason TEXT;
        CREATE TABLE absences(id INTEGER PRIMARY KEY,account_id INTEGER,
          start_date TEXT,end_date TEXT,start_time INTEGER,end_time INTEGER,
          reason TEXT,is_excused INTEGER);
        UPDATE lessons SET was_absent=1, absence_reason='Verspätet' WHERE id=1;
        ''')
        day = c.execute('SELECT date FROM lessons WHERE id=1').fetchone()[0]
        c.execute('INSERT INTO absences VALUES(1,1,?,?,800,803,?,1)', (day, day, 'Verspätet'))
    return client, day


@pytest.mark.parametrize('reason,end', [('Verspätet',803), (' Verspätet ',850), ('Verspätung',900)])
def test_lateness_ignored_without_duration_threshold_and_feedback_saved(env, reason, end):
    client, day = seed(env)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('UPDATE absences SET reason=?,end_time=?', (reason,end))
    with closing(db.history_conn()) as c:
        assert c.execute('SELECT was_absent,absence_reason FROM lessons WHERE id=1').fetchone()[:] == (0,None)
        # No rewriting source records; future source sync can still correct them.
        assert c.execute('SELECT was_absent FROM main.lessons WHERE id=1').fetchone()[0] == 1
        assert c.execute('SELECT COUNT(*) FROM absences').fetchone()[0] == 1
    assert _gap(1, date.fromisoformat(day))['total_lessons'] == 5
    assert post(client,1,rating=3).status_code == 200
    assert _gap(1, date.fromisoformat(day))['unrated_lessons'] == 4


@pytest.mark.parametrize('reason', ['Abwesend', 'Krank', None])
def test_real_absence_wins_even_if_lateness_overlaps(env, reason):
    _,day=seed(env)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('INSERT INTO absences VALUES(2,1,?,?,800,900,?,0)', (day,day,reason))
    with closing(db.history_conn()) as c:
        assert c.execute('SELECT was_absent FROM lessons WHERE id=1').fetchone()[0] == 1


def test_other_account_and_nonoverlapping_lateness_do_not_erase_absence(env):
    seed(env)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('UPDATE absences SET account_id=2')
    with closing(db.history_conn()) as c:
        assert c.execute('SELECT was_absent FROM lessons WHERE id=1').fetchone()[0] == 1
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute('UPDATE absences SET account_id=1,start_time=900,end_time=903')
    with closing(db.history_conn()) as c:
        assert c.execute('SELECT was_absent FROM lessons WHERE id=1').fetchone()[0] == 1


def test_archive_recompute_repairs_old_flags_and_keeps_real_absences(env):
    _, day=seed(env)
    # Exercise the production archive method on the same synthetic database.
    store=object.__new__(UntisStorage)
    store._conn=sqlite3.connect(db.SETTINGS.history_db_path)
    store._conn.row_factory=sqlite3.Row
    store._write_lock=RLock()
    try:
        assert store.recompute_attendance(1,day,day) == 0
        assert store._conn.execute('SELECT was_absent,absence_reason FROM lessons WHERE id=1').fetchone()[:] == (0,None)
        store._conn.execute('INSERT INTO absences VALUES(2,1,?,?,800,900,?,0)', (day,day,'Abwesend'))
        store._conn.commit()
        assert store.recompute_attendance(1,day,day) == 5
        assert store._conn.execute('SELECT absence_reason FROM lessons WHERE id=1').fetchone()[0] == 'Abwesend'
    finally:
        store._conn.close()


def test_read_export_uses_corrected_attendance_preserving_cursors_and_raw_events(env):
    from backend.routers import read_access as r
    client,_=seed(env)
    patch=env[2]
    client.app.include_router(r.router,prefix='/api')
    patch.setattr(r,'SETTINGS',db.SETTINGS)
    patch.setenv('LEARNING_READ_TOKEN','a'*48)
    patch.setenv('LEARNING_READ_ACCOUNTS','1')
    headers={'X-Learning-Read-Key':'a'*48}
    base='/api/integration/learning/'
    first=client.get(base+'lessons?account_id=1&limit=1',headers=headers).json()
    assert first['rows'][0]['id'] == first['rows'][0]['_cursor'] == 1
    assert first['rows'][0]['was_absent'] == 0
    assert first['rows'][0]['absence_reason'] is None
    assert first['next_after'] == 1 and first['has_more']
    second=client.get(base+'lessons?account_id=1&after=1',headers=headers).json()
    assert [x['id'] for x in second['rows']] == [2,3,4,5]
    assert not second['has_more']
    raw=client.get(base+'absences?account_id=1',headers=headers).json()
    assert raw['rows'][0]['reason'] == 'Verspätet'
    with closing(r.open_readonly('archive')) as c:
        with pytest.raises(sqlite3.OperationalError):
            c.execute('UPDATE main.lessons SET was_absent=0')
