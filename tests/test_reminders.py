from contextlib import closing
from datetime import datetime
from test_learning import env, child
from backend import db, reminders as r
from backend.routers import reminders as routes
import pytest

NOW=datetime(2026,9,14,18,0,tzinfo=r.ZONE)
URL='/api/accounts/1/reminders'

def setup(env):
    client,state,patch=env
    client.app.include_router(routes.router,prefix='/api')
    return client,state,patch

def app_device(patch, sent, service='mobile_app_kind_iphone'):
    """Ein Kindergerät über die Home-Assistant-App; `sent` sammelt die Mitteilungen."""
    from backend import app_notify
    patch.setattr(app_notify,'own_panel',lambda:'/e54108c7_schul_cockpit')
    app_notify.set_targets(1,[service])
    patch.setattr(app_notify,'send',lambda service,title,message,url:(sent.append((service,title,message,url)) or True))

def test_defaults_permissions_and_explicit_time(env):
    client,state,_=setup(env)
    assert not client.get(URL).json()['enabled']
    assert client.put(URL,json={'enabled':True}).status_code==422
    assert client.put(URL,json={'enabled':True,'remind_at':'23:00'}).status_code==422
    assert client.put(URL,json={'enabled':True,'remind_at':'18:00'}).status_code==200
    child(state)
    assert client.get(URL).json()['remind_at']=='18:00'
    assert client.put(URL,json={'enabled':False}).status_code==403
    assert client.get('/api/accounts/2/reminders').status_code==403

def test_bundled_once_and_persistent_across_restart(env):
    client,_,patch=setup(env);sent=[];app_device(patch,sent)
    client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    patch.setattr(r,'snapshot',lambda *a:dict(homework=2,material=3,feedback=1))
    r.run_once(NOW);db.init_webapp_db();r.run_once(NOW)
    assert len(sent)==1
    assert 'Hausaufgaben' in sent[0][2] and 'Schultasche' in sent[0][2]
    assert client.get(URL).json()['last_app_delivery']['status']=='accepted'

def test_no_reminder_when_done_outside_window_disabled_or_source_unavailable(env):
    client,_,patch=setup(env);sent=[];app_device(patch,sent)
    client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    patch.setattr(r,'snapshot',lambda *a:dict(homework=0,material=0,feedback=0))
    r.run_once(NOW)
    patch.setattr(r,'snapshot',lambda *a:dict(homework=1,material=0,feedback=0))
    r.run_once(NOW.replace(hour=17));r.run_once(NOW.replace(hour=19));r.run_once(NOW.replace(hour=23))
    def broken(*a):raise RuntimeError('source missing')
    patch.setattr(r,'snapshot',broken);r.run_once(NOW)
    client.put(URL,json={'enabled':False});r.run_once(NOW)
    assert sent==[]
    assert client.get(URL).json()['last_app_delivery'] is None

def test_failed_delivery_is_recorded_and_not_replayed(env):
    client,_,patch=setup(env);client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    from backend import app_notify
    patch.setattr(app_notify,'own_panel',lambda:'/x');app_notify.set_targets(1,['mobile_app_kind_iphone'])
    calls=[];patch.setattr(app_notify,'send',lambda *a:(calls.append(1) or False))
    patch.setattr(r,'snapshot',lambda *a:dict(homework=0,material=1,feedback=0))
    r.run_once(NOW);r.run_once(NOW)
    assert calls==[1]
    assert client.get(URL).json()['last_app_delivery']['status']=='failed'

def test_web_push_is_gone(env):
    """D65: keine Abonnements, keine Schlüssel, keine Route."""
    client,_,_=setup(env)
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE name='push_subscriptions'").fetchone() is None
        assert c.execute("SELECT COUNT(*) FROM schema_meta WHERE key LIKE 'vapid:%'").fetchone()[0]==0
    assert 'devices' not in client.get(URL).json()
    assert client.get('/api/push/vapid-key').status_code==404

def test_snapshot_uses_due_tasks_material_and_ended_feedback(env):
    """Rückmeldungen: beendete, gehaltene Stunden ohne Bewertung, auch vergessene
    der Vortage ab rewards.FEEDBACK_FROM (D210)."""
    import sqlite3
    from test_day_close import LESSON_COLUMNS
    _,_,patch=setup(env)
    patch.setattr(r,'packing_plan',lambda account,day:([dict(key='subject:math',label='Mathematik')],'x',[]))
    with sqlite3.connect(db.SETTINGS.history_db_path) as h:
        h.execute(f"CREATE TABLE IF NOT EXISTS lessons({LESSON_COLUMNS})")
        h.executemany("INSERT INTO lessons(id,account_id,date,start_time,end_time,subject_name,code,was_absent) VALUES(?,1,?,?,?,'Mathematik',?,0)",
                      [(1,'2026-09-14',915,1000,None),(2,'2026-09-14',1815,1900,None),(3,'2026-09-14',1015,1100,'cancelled'),
                       (4,'2026-09-11',800,845,None),(5,'2026-07-10',800,845,None)])
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO tasks(account_id,title,status,source,due_date,created_at,updated_at) VALUES(1,'Aufgabe','open','manual','2026-09-15','now','now')")
    # Heute um 10 Uhr offen, die Stunde bis 19 Uhr läuft noch, die ausgefallene zählt nicht.
    # Vortage zählen erst ab rewards.FEEDBACK_FROM (21.09.); dieser Test spielt davor.
    assert r.snapshot(1,NOW)==dict(homework=1,material=1,feedback=1,photos=0)
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE tasks SET status='done'")
        c.execute("INSERT INTO packing_items VALUES(1,'2026-09-15','subject:math',1,1,'now',2)")
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,1,1,3,'now','now')")
    assert r.snapshot(1,NOW)==dict(homework=0,material=0,feedback=0,photos=0)

def test_the_morning_snapshot_checks_todays_bag_and_skips_skipped_tasks(env):
    """Morgens zählt die Tasche von gestern Abend, also die für heute, und nur
    Aufgaben, die heute oder früher fällig und offen sind."""
    _,_,patch=setup(env)
    today=NOW.date().isoformat()
    def plan(account,day):
        return ([dict(key='subject:math',label='Mathematik')],'x',[]) if day==NOW.date() else ([dict(key='subject:bio',label='Biologie')],'x',[])
    patch.setattr(r,'packing_plan',plan)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO packing_items VALUES(1,?,'subject:math',1,1,'now',2)",(today,))
        c.execute("INSERT INTO tasks(account_id,title,status,source,due_date,created_at,updated_at) VALUES(1,'Morgen','open','manual','2026-09-15','now','now')")
        c.execute("INSERT INTO tasks(account_id,title,status,source,due_date,created_at,updated_at) VALUES(1,'Übersprungen','skipped','manual','2026-09-01','now','now')")
    morning=r.snapshot(1,NOW,morning=True)
    assert (morning['material'],morning['homework'])==(0,0)
    evening=r.snapshot(1,NOW)
    assert (evening['material'],evening['homework'])==(1,1)


def test_account_remap_keeps_settings_packing_and_delivery_with_child(env):
    from backend.reconcile import _reconcile_accounts
    client,_,_=setup(env)
    client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    _reconcile_accounts()
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO packing_items VALUES(1,'2026-09-15','subject:math',1,1,'now',2)")
        c.execute("INSERT INTO reminder_deliveries VALUES(1,'2026-09-14',99,'accepted','now','now')")
    import sqlite3
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:c.execute('UPDATE accounts SET id=11 WHERE id=1')
    _reconcile_accounts()
    with closing(db.webapp_conn()) as c:
        for table in ('packing_items','reminder_settings','reminder_deliveries'):
            assert c.execute(f'SELECT account_id FROM {table}').fetchone()[0]==11


def test_the_app_reminder_goes_out_once_per_device_and_day(env):
    client,_,patch=setup(env)
    from backend import app_notify
    client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    patch.setattr(r,'snapshot',lambda *a:dict(homework=1,material=2,feedback=0))
    patch.setattr(app_notify,'own_panel',lambda:'/e54108c7_schul_cockpit')
    app_notify.set_targets(1,['mobile_app_kind_iphone'])
    sent=[]
    patch.setattr(app_notify,'send',lambda service,title,message,url:(sent.append((service,message,url)) or True))
    r.run_once(NOW)
    r.run_once(NOW)
    assert len(sent)==1
    service,message,url=sent[0]
    assert service=='mobile_app_kind_iphone'
    # Was offen ist, steht in der Nachricht; das Antippen führt in die App.
    assert 'Hausaufgaben' in message and 'Schultasche' in message
    assert 'Rückmeldungen' not in message
    assert url=='/e54108c7_schul_cockpit'
    assert client.get(URL).json()['last_app_delivery']['status']=='accepted'


def test_only_companion_app_services_can_be_chosen(env):
    client,state,patch=setup(env)
    from backend import app_notify
    patch.setattr(app_notify,'services',lambda:['mobile_app_kind_iphone','mobile_app_eltern_iphone'])
    assert client.put(URL+'/targets',json={'services':['notify.persistent_notification']}).status_code==422
    ok=client.put(URL+'/targets',json={'services':['mobile_app_kind_iphone']})
    assert ok.status_code==200 and ok.json()['app_targets']==['mobile_app_kind_iphone']
    # Ein zusammengesetzter Name darf keinen anderen Dienst treffen.
    assert app_notify.set_targets(1,['mobile_app_x/../../core'])==[]
    child(state)
    assert client.put(URL+'/targets',json={'services':[]}).status_code==403


def test_the_day_view_follows_the_reminder_time(env):
    client,_,patch=setup(env)
    from backend.routers import today as today_routes
    # Der Stundenplan spielt hier keine Rolle, nur die Abendgrenze.
    patch.setattr(today_routes,'lessons_for_date',lambda conn,account,day:[])
    patch.setattr(today_routes,'upcoming_exams',lambda conn,account,days_ahead=7:[])
    patch.setattr(today_routes,'hidden_keys',lambda account:set())
    client.app.include_router(today_routes.router,prefix='/api')
    assert client.get('/api/accounts/1/today').json()['evening_from']=='18:00'
    client.put(URL,json={'enabled':True,'remind_at':'17:30'})
    assert client.get('/api/accounts/1/today').json()['evening_from']=='17:30'
