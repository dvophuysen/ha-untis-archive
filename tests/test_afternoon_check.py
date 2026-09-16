"""Die Frage nach der Schule: Mitteilung, Karte, Foto und die Aufgabe daraus."""
import io
import sqlite3
from contextlib import closing
from datetime import datetime

from PIL import Image

from test_learning import env, child
from test_day_close import LESSON_COLUMNS
from backend import afternoon_check as ac, db, reminders as r
from backend.routers import afternoon_check as routes
from backend.routers import reminders as reminder_routes

MONDAY = '2026-09-14'
URL = '/api/accounts/1/afternoon-check'
SETTINGS = '/api/accounts/1/reminders'


def at(hour, minute=0, day=14):
    return datetime(2026, 9, day, hour, minute, tzinfo=ac.ZONE)


def setup(env):
    client, state, patch = env
    client.app.include_router(routes.router, prefix='/api')
    client.app.include_router(reminder_routes.router, prefix='/api')
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f'CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})')
        rows = [
            (1, MONDAY, 800, 845, 'Mathematik', None),
            (2, MONDAY, 900, 945, 'LATEIN', None),
            (3, MONDAY, 1000, 1045, 'Englisch', 'cancelled'),   # ausgefallen: zählt nicht als Ende
            (4, '2026-09-15', 800, 845, 'Mathematik', None),
            (5, '2026-09-16', 800, 845, 'LATEIN', None),
            (6, '2026-09-17', 800, 845, 'LATEIN', None),
        ]
        for i, day, start, end, subject, code in rows:
            c.execute('INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) '
                      'VALUES(?,1,?,?,?,?,?,0)', (i, day, start, end, subject, code))
    return client, state, patch


def device(patch, sent):
    from backend import app_notify
    patch.setattr(app_notify, 'own_panel', lambda: '/e54108c7_schul_cockpit')
    app_notify.set_targets(1, ['mobile_app_kind_iphone'])
    patch.setattr(app_notify, 'send', lambda service, title, message, url: (sent.append((service, title, message, url)) or True))


def enable(client, **extra):
    body = dict({'enabled': True, 'remind_at': '18:00', 'afternoon_enabled': True}, **extra)
    assert client.put(SETTINGS, json=body).status_code == 200


def png():
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (200, 200, 200)).save(buf, format='PNG')
    return buf.getvalue()


def test_settings_roundtrip_and_default_off(env):
    client, state, _ = setup(env)
    first = client.get(SETTINGS).json()
    assert first['afternoon_enabled'] is False and first['afternoon_delay'] == 20
    enable(client, afternoon_delay=30)
    saved = client.get(SETTINGS).json()
    assert saved['afternoon_enabled'] is True and saved['afternoon_delay'] == 30
    assert client.put(SETTINGS, json={'enabled': False, 'afternoon_enabled': True, 'afternoon_delay': 999}).status_code == 422
    child(state)
    assert client.put(SETTINGS, json={'enabled': False, 'afternoon_enabled': False}).status_code == 403


def test_the_question_goes_out_once_after_the_last_lesson(env):
    client, _, patch = setup(env)
    sent = []
    device(patch, sent)
    patch.setattr(r, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    enable(client)
    # Letzte Stunde endet 09:45 (die ausgefallene 10:45 zählt nicht); 20 Minuten später ist es fällig.
    r.run_once(at(9, 50))
    assert sent == []
    r.run_once(at(10, 5))
    r.run_once(at(10, 12))
    assert len(sent) == 1
    service, title, message, url = sent[0]
    assert service == 'mobile_app_kind_iphone' and 'notiert' in title and 'Foto' in message
    assert url == '/e54108c7_schul_cockpit'
    # Stunden später wird nichts nachgeliefert; am Wochenende ohne Stunden auch nicht.
    r.run_once(at(13, 0))
    r.run_once(at(10, 5, day=19))
    assert len(sent) == 1


def test_no_question_when_disabled_or_already_answered(env):
    client, _, patch = setup(env)
    sent = []
    device(patch, sent)
    patch.setattr(r, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    enable(client, afternoon_enabled=False)
    r.run_once(at(10, 5))
    assert sent == []
    enable(client)
    patch.setattr(ac, 'now_local', lambda: at(9, 50))
    assert client.post(URL + '/nothing').status_code == 200
    r.run_once(at(10, 5))
    assert sent == []


def test_the_card_is_active_between_last_lesson_and_evening(env):
    client, _, patch = setup(env)
    patch.setattr(ac, 'now_local', lambda: at(9, 0))
    before = client.get(URL).json()
    assert before['school_day'] and before['last_lesson_end'] == '09:45' and not before['active']
    patch.setattr(ac, 'now_local', lambda: at(14, 0))
    assert client.get(URL).json()['active']
    patch.setattr(ac, 'now_local', lambda: at(18, 30))
    assert not client.get(URL).json()['active']
    patch.setattr(ac, 'now_local', lambda: at(14, 0, day=19))
    weekend = client.get(URL).json()
    assert not weekend['school_day'] and not weekend['active']
    # „Nichts Neues“ schließt die Frage für heute.
    patch.setattr(ac, 'now_local', lambda: at(14, 0))
    closed = client.post(URL + '/nothing').json()
    assert closed['closed'] and not closed['active'] and closed['answers'][0]['answer'] == 'nothing'


def test_a_photo_creates_the_task_at_once_and_the_reading_fills_it_in(env):
    client, state, patch = setup(env)
    patch.setattr(ac, 'now_local', lambda: at(14, 0))
    child(state)

    async def fake_analyze(account_id, material_id):
        with closing(db.webapp_conn()) as c, c:
            c.execute("UPDATE materials SET subject_name='LATEIN',title='Begleitband S. 13 Aufgabe C',"
                      "analysis_state='ready' WHERE id=?", (material_id,))
        ac.refine(account_id, material_id)
    patch.setattr(routes.analysis, 'analyze', fake_analyze)

    saved = client.post(URL + '/photo', files={'file': ('foto.png', png(), 'image/png')}).json()
    assert saved['state']['photos'] == 1 and saved['state']['active']
    with closing(db.webapp_conn()) as c:
        task = dict(c.execute('SELECT * FROM tasks WHERE id=?', (saved['task_id'],)).fetchone())
        link = c.execute("SELECT 1 FROM material_links WHERE material_id=? AND kind='task' AND target_id=?",
                         (saved['material_id'], saved['task_id'])).fetchone()
        check = dict(c.execute('SELECT * FROM afternoon_checks WHERE material_id=?', (saved['material_id'],)).fetchone())
    # Die Lesung (im Test sofort) hat Fach, Titel und den Termin der nächsten Lateinstunde eingetragen.
    assert task['subject_name'] == 'LATEIN'
    assert task['title'] == 'Latein: Begleitband S. 13 Aufgabe C'
    assert task['due_date'] == '2026-09-16' and task['task_type'] == 'homework' and task['status'] == 'open'
    assert task['source'] == 'manual' and task['created_by_user_id'] == 2
    assert link is not None and check['answer'] == 'photo' and check['refined_at']
    # Eine zweite Lesung ändert nichts mehr.
    assert ac.refine(1, saved['material_id']) is None


def test_without_reading_the_task_stays_provisional_until_the_next_school_day(env):
    client, _, patch = setup(env)
    patch.setattr(ac, 'now_local', lambda: at(14, 0))

    async def never(account_id, material_id):
        return None
    patch.setattr(routes.analysis, 'analyze', never)
    saved = client.post(URL + '/photo', files={'file': ('foto.png', png(), 'image/png')}).json()
    with closing(db.webapp_conn()) as c:
        task = dict(c.execute('SELECT * FROM tasks WHERE id=?', (saved['task_id'],)).fetchone())
    assert task['title'] == ac.PROVISIONAL_TITLE and task['due_date'] == '2026-09-15'
    # Ohne fertige Lesung trägt refine nichts ein.
    assert ac.refine(1, saved['material_id']) is None


def test_a_reading_without_subject_keeps_the_provisional_due_date(env):
    client, _, patch = setup(env)
    patch.setattr(ac, 'now_local', lambda: at(14, 0))

    async def unclear(account_id, material_id):
        with closing(db.webapp_conn()) as c, c:
            c.execute("UPDATE materials SET title='Aufgabe 3 und 4',analysis_state='ready' WHERE id=?", (material_id,))
        ac.refine(account_id, material_id)
    patch.setattr(routes.analysis, 'analyze', unclear)
    saved = client.post(URL + '/photo', files={'file': ('foto.png', png(), 'image/png')}).json()
    with closing(db.webapp_conn()) as c:
        task = dict(c.execute('SELECT * FROM tasks WHERE id=?', (saved['task_id'],)).fetchone())
    assert task['title'] == 'Aufgabe 3 und 4' and task['subject_name'] is None and task['due_date'] == '2026-09-15'


def test_the_task_is_not_touched_once_someone_closed_it(env):
    client, _, patch = setup(env)
    patch.setattr(ac, 'now_local', lambda: at(14, 0))

    async def never(account_id, material_id):
        return None
    patch.setattr(routes.analysis, 'analyze', never)
    saved = client.post(URL + '/photo', files={'file': ('foto.png', png(), 'image/png')}).json()
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE tasks SET status='done' WHERE id=?", (saved['task_id'],))
        c.execute("UPDATE materials SET subject_name='LATEIN',title='x',analysis_state='ready' WHERE id=?", (saved['material_id'],))
    assert ac.refine(1, saved['material_id']) is None
