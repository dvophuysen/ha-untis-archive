"""Der abgeleitete Tagesabschluss: Morgenmitteilung und Verlässlichkeit.

Es gibt keinen Knopf. Ein Abend gilt als erledigt, sobald nichts mehr offen
ist — dieselben drei Zahlen, über die auch die Erinnerung entscheidet.
"""
import sqlite3
from contextlib import closing
from datetime import date, datetime

from test_learning import env
from backend import db, day_close, reminders as r
from backend.routers import reminders as reminder_routes

NOW = datetime(2026, 9, 14, 19, 30, tzinfo=r.ZONE)      # Montagabend
MORNING = datetime(2026, 9, 15, 6, 45, tzinfo=r.ZONE)   # Dienstagfrüh

LESSON_COLUMNS = ("id INTEGER PRIMARY KEY, account_id INTEGER, untis_period_id INTEGER, date TEXT, "
                  "start_time INTEGER, end_time INTEGER, subject_untis_id INTEGER, subject_name TEXT, "
                  "teacher_untis_id INTEGER, teacher_name TEXT, teacher_orig_name TEXT, room TEXT, "
                  "room_orig TEXT, subject_orig_name TEXT, is_teacher_substituted INTEGER, "
                  "is_room_substituted INTEGER, is_subject_substituted INTEGER, code TEXT, lstext TEXT, "
                  "subst_text TEXT, info TEXT, was_absent INTEGER, absence_reason TEXT, "
                  "is_late_addition INTEGER, period_info_json TEXT, payload_json TEXT")


def setup(env):
    client, state, patch = env
    client.app.include_router(reminder_routes.router, prefix='/api')
    return client, state, patch


def stand(patch, **counts):
    # Was der Erinnerungsdienst abends sieht; leer heißt erledigt.
    patch.setattr(r, 'snapshot', lambda *a, **kw: dict(dict(homework=0, material=0, feedback=0), **counts))


def lessons(*days, cancelled=()):
    # Schultage im Verlauf anlegen; ohne sie zählt kein Abend.
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute(f'CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})')
        for i, day in enumerate(days, start=1):
            c.execute('INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) '
                      'VALUES(?,1,?,800,845,?,?,0)',
                      (i, day, 'Mathematik', 'cancelled' if day in cancelled else None))


def enable(client, **extra):
    client.put('/api/accounts/1/reminders', json=dict({'enabled': True, 'remind_at': '18:00'}, **extra))


def test_the_evening_counts_as_done_once_nothing_is_open(env):
    client, _, patch = setup(env)
    enable(client)
    day = NOW.date().isoformat()
    stand(patch, homework=1)
    r.run_once(NOW)
    assert day_close.closure(1, day) is None, 'Offenes zählt nicht als erledigt'
    stand(patch)
    r.run_once(NOW)
    done = day_close.closure(1, day)
    assert done['closed_by'] == 'erledigt' and done['after_reminder'] == 0
    # Läuft später etwas nach, bleibt der Moment stehen, in dem es fertig war.
    stand(patch, homework=1)
    r.run_once(NOW.replace(hour=21))
    assert day_close.closure(1, day)['closed_at'] == done['closed_at']


def test_being_done_only_after_the_reminder_is_marked_as_such(env):
    client, _, patch = setup(env)
    enable(client)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO reminder_app_deliveries VALUES(1,?,'mobile_app_kind','accepted','now')",
                  (NOW.date().isoformat(),))
    stand(patch)
    r.run_once(NOW)
    assert day_close.closure(1, NOW.date().isoformat())['after_reminder'] == 1


def test_only_evenings_before_a_school_day_count_and_only_unprompted_ones(env):
    setup(env)
    # Mo–Mi Unterricht, Do ausgefallen: dann zählt der Mittwochabend nicht.
    lessons('2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', cancelled=('2026-09-17',))
    with closing(db.webapp_conn()) as c:
        c.executescript(
            "INSERT INTO day_closures VALUES(1,'2026-09-13','2026-09-13T17:00','erledigt',0,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-14','2026-09-14T20:00','erledigt',1,0,0,0);"
            "INSERT INTO day_closures VALUES(1,'2026-09-15','2026-09-15T20:00','erledigt',1,0,0,0);")
    week = day_close.reliability(1, date(2026, 9, 16))['current']
    # Sonntag-, Montag- und Dienstagabend stehen vor einem Schultag; der
    # Mittwochabend nicht, weil der Donnerstag ausfällt.
    assert week['evenings'] == 3 and week['closed'] == 3
    # Nur am Sonntag war vor der Erinnerung alles fertig.
    assert week['own'] == 1


def test_the_morning_notification_only_reaches_who_was_not_done(env):
    client, _, patch = setup(env)
    from backend import app_notify
    lessons('2026-09-15')
    enable(client, morning_enabled=True)
    stand(patch, homework=1, feedback=3)
    patch.setattr(r, 'packing_plan', lambda account, day: ([dict(key='m', label='Mathe')], 'x', [dict(id=1)]))
    patch.setattr(app_notify, 'own_panel', lambda: '/e54108c7_schul_cockpit')
    app_notify.set_targets(1, ['mobile_app_kind_iphone'])
    sent = []
    patch.setattr(app_notify, 'send', lambda service, title, message, url: (sent.append((title, message)) or True))
    r.run_once(MORNING)
    r.run_once(MORNING)          # einmal je Tag und Gerät
    assert len(sent) == 1 and sent[0][0] == 'Vor dem Aufbruch'
    # Rückmeldungen ändern morgens nichts mehr und stehen deshalb nicht drin.
    assert 'Hausaufgaben' in sent[0][1] and 'Rückmeldungen' not in sent[0][1]


def test_no_morning_notification_when_done_on_a_free_day_or_switched_off(env):
    client, _, patch = setup(env)
    from backend import app_notify
    lessons('2026-09-15')
    enable(client, morning_enabled=True)
    stand(patch, homework=1, material=1)
    patch.setattr(app_notify, 'own_panel', lambda: '/panel')
    app_notify.set_targets(1, ['mobile_app_kind_iphone'])
    sent = []
    patch.setattr(app_notify, 'send', lambda *a: (sent.append(a) or True))

    patch.setattr(r, 'packing_plan', lambda account, day: ([], 'x', []))
    r.run_once(MORNING)                                    # kein Unterricht: nichts
    patch.setattr(r, 'packing_plan', lambda account, day: ([], 'x', [dict(id=1, is_cancelled=True)]))
    r.run_once(MORNING)                                    # alles fällt aus: nichts
    patch.setattr(r, 'packing_plan', lambda account, day: ([dict(key='m', label='Mathe')], 'x', [dict(id=1)]))
    enable(client, morning_enabled=False)
    r.run_once(MORNING)                                    # abgeschaltet: nichts
    enable(client, morning_enabled=True)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO day_closures VALUES(1,'2026-09-14','2026-09-14T19:00','erledigt',0,0,0,0)")
    r.run_once(MORNING)                                    # gestern fertig: nichts
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
