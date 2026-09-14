"""Der Tagesabschluss und was daran hängt: Morgenmitteilung und Verlässlichkeit."""
import sqlite3
from contextlib import closing
from datetime import date, datetime

from test_learning import env, child
from backend import db, day_close, reminders as r
from backend.routers import day_close as routes, reminders as reminder_routes, today as today_routes

NOW = datetime(2026, 9, 14, 19, 30, tzinfo=r.ZONE)      # Montagabend
MORNING = datetime(2026, 9, 15, 6, 45, tzinfo=r.ZONE)   # Dienstagfrüh
URL = '/api/accounts/1/day-close'

LESSON_COLUMNS = ("id INTEGER PRIMARY KEY, account_id INTEGER, untis_period_id INTEGER, date TEXT, "
                  "start_time INTEGER, end_time INTEGER, subject_untis_id INTEGER, subject_name TEXT, "
                  "teacher_untis_id INTEGER, teacher_name TEXT, teacher_orig_name TEXT, room TEXT, "
                  "room_orig TEXT, subject_orig_name TEXT, is_teacher_substituted INTEGER, "
                  "is_room_substituted INTEGER, is_subject_substituted INTEGER, code TEXT, lstext TEXT, "
                  "subst_text TEXT, info TEXT, was_absent INTEGER, absence_reason TEXT, "
                  "is_late_addition INTEGER, period_info_json TEXT, payload_json TEXT")


def setup(env):
    client, state, patch = env
    client.app.include_router(routes.router, prefix='/api')
    client.app.include_router(reminder_routes.router, prefix='/api')
    return client, state, patch


def lessons(*days, cancelled=()):
    """Schultage im Verlauf anlegen — ohne sie zählt nichts als Schultag."""
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f'CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})')
        for i, day in enumerate(days, start=1):
            c.execute('INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) '
                      'VALUES(?,1,?,800,845,?,?,0)',
                      (i, day, 'Mathematik', 'cancelled' if day in cancelled else None))


def test_the_close_records_who_did_it_and_whether_the_reminder_had_gone_out(env):
    client, state, patch = setup(env)
    patch.setattr(routes, 'snapshot', lambda *a: dict(homework=2, material=1, feedback=0))
    child(state)
    body = client.post(URL).json()
    assert body['closed']['closed_by'] == 'kind'
    assert body['closed']['after_reminder'] == 0
    # Offene Punkte sperren den Knopf nicht, sie werden festgehalten.
    assert body['closed']['open_homework'] == 2 and body['closed']['open_material'] == 1
    first = body['closed']['closed_at']
    # Ein zweiter Druck schönt das Bild nicht.
    patch.setattr(routes, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    again = client.post(URL).json()['closed']
    assert again['closed_at'] == first and again['open_homework'] == 2
    assert client.get(URL).json()['closed']['closed_by'] == 'kind'


def test_a_close_after_the_reminder_is_marked_as_such(env):
    client, state, patch = setup(env)
    patch.setattr(routes, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO reminder_app_deliveries VALUES(1,?,'mobile_app_kind','accepted','now')",
                  (date.today().isoformat(),))
    child(state)
    assert client.post(URL).json()['closed']['after_reminder'] == 1


def test_the_parent_close_is_not_counted_as_the_child_s_own(env):
    client, _, patch = setup(env)
    patch.setattr(routes, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    assert client.post(URL).json()['closed']['closed_by'] == 'eltern'


def test_only_evenings_before_a_school_day_count_and_only_unprompted_own_closes(env):
    setup(env)
    # Mo–Mi Unterricht, Do ausgefallen: dann zählt der Mittwochabend nicht.
    lessons('2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', cancelled=('2026-09-17',))
    with closing(db.webapp_conn()) as c:
        c.executescript(
            "INSERT INTO day_closures VALUES(1,'2026-09-13','2026-09-13T19:00','kind',0,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-14','2026-09-14T20:00','kind',1,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-15','2026-09-15T20:00','eltern',0,0,0,0);")
    week = day_close.reliability(1, date(2026, 9, 16))['current']
    # Sonntag-, Montag- und Dienstagabend stehen vor einem Schultag; der
    # Mittwochabend nicht, weil der Donnerstag ausfällt.
    assert week['evenings'] == 3 and week['closed'] == 3
    # Nur der Sonntag war selbst und ohne Erinnerung.
    assert week['own'] == 1


def test_the_morning_notification_only_reaches_who_did_not_close(env):
    client, _, patch = setup(env)
    from backend import app_notify
    lessons('2026-09-15')
    client.put('/api/accounts/1/reminders',
               json={'enabled': True, 'remind_at': '18:00', 'morning_enabled': True})
    patch.setattr(r, 'snapshot', lambda *a: dict(homework=1, material=0, feedback=3))
    patch.setattr(r, 'packing_plan', lambda account, day: ([], 'x', [dict(id=1)]))
    patch.setattr(app_notify, 'own_panel', lambda: '/e54108c7_schul_cockpit')
    app_notify.set_targets(1, ['mobile_app_kind_iphone'])
    sent = []
    patch.setattr(app_notify, 'send', lambda service, title, message, url: (sent.append((title, message)) or True))
    r.run_once(MORNING)
    r.run_once(MORNING)          # einmal je Tag und Gerät
    assert len(sent) == 1 and sent[0][0] == 'Vor dem Aufbruch'
    # Rückmeldungen ändern morgens nichts mehr und stehen deshalb nicht drin.
    assert 'Hausaufgaben' in sent[0][1] and 'Rückmeldungen' not in sent[0][1]


def test_no_morning_notification_after_a_close_on_a_free_day_or_when_switched_off(env):
    client, _, patch = setup(env)
    from backend import app_notify
    lessons('2026-09-15')
    on = {'enabled': True, 'remind_at': '18:00', 'morning_enabled': True}
    client.put('/api/accounts/1/reminders', json=on)
    patch.setattr(r, 'snapshot', lambda *a: dict(homework=1, material=1, feedback=0))
    patch.setattr(app_notify, 'own_panel', lambda: '/panel')
    app_notify.set_targets(1, ['mobile_app_kind_iphone'])
    sent = []
    patch.setattr(app_notify, 'send', lambda *a: (sent.append(a) or True))

    patch.setattr(r, 'packing_plan', lambda account, day: ([], 'x', []))
    r.run_once(MORNING)                                    # kein Unterricht: nichts
    patch.setattr(r, 'packing_plan', lambda account, day: ([], 'x', [dict(id=1)]))
    client.put('/api/accounts/1/reminders',
               json={'enabled': True, 'remind_at': '18:00', 'morning_enabled': False})
    r.run_once(MORNING)                                    # abgeschaltet: nichts
    client.put('/api/accounts/1/reminders', json=on)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO day_closures VALUES(1,'2026-09-14','2026-09-14T19:00','kind',0,0,0,0)")
    r.run_once(MORNING)                                    # abgeschlossen: nichts
    assert sent == []


def test_the_morning_time_stays_inside_the_morning(env):
    client, _, _ = setup(env)
    url = '/api/accounts/1/reminders'
    assert client.put(url, json={'enabled': True, 'remind_at': '18:00', 'morning_at': '13:00'}).status_code == 422
    # Ab Werk aus: die Morgenmitteilung wird verabredet, nicht ausgeliefert.
    assert client.get(url).json()['morning_enabled'] is False
    ok = client.put(url, json={'enabled': True, 'remind_at': '18:00',
                               'morning_enabled': True, 'morning_at': '07:10'})
    assert ok.status_code == 200 and ok.json()['morning_at'] == '07:10'
    assert client.get(url).json()['morning_enabled'] is True


def test_the_day_view_carries_the_close(env):
    client, state, patch = setup(env)
    patch.setattr(today_routes, 'lessons_for_date', lambda conn, account, day: [])
    patch.setattr(today_routes, 'upcoming_exams', lambda conn, account, days_ahead=7: [])
    patch.setattr(today_routes, 'hidden_keys', lambda account: set())
    patch.setattr(routes, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    client.app.include_router(today_routes.router, prefix='/api')
    assert client.get('/api/accounts/1/today').json()['day_close']['closed'] is None
    child(state)
    client.post(URL)
    assert client.get('/api/accounts/1/today').json()['day_close']['closed']['closed_by'] == 'kind'


def test_a_read_only_account_cannot_close_someone_else_s_day(env):
    client, state, patch = setup(env)
    patch.setattr(routes, 'snapshot', lambda *a: dict(homework=0, material=0, feedback=0))
    child(state, 3)
    assert client.post(URL).status_code == 403
    assert client.get(URL).status_code == 403
