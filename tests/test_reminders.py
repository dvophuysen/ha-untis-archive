from contextlib import closing
from datetime import datetime
from test_learning import env, child
from backend import db, reminders as r
from backend.routers import reminders as routes
from backend.routers.push import SubscribeIn
import pytest

NOW=datetime(2026,9,14,18,0,tzinfo=r.ZONE)
URL='/api/accounts/1/reminders'

def setup(env):
    client,state,patch=env
    client.app.include_router(routes.router,prefix='/api')
    return client,state,patch

def subscribe(uid=2):
    with closing(db.webapp_conn()) as c:
        return c.execute("INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,created_at,last_seen_at) VALUES(?,?,?,?,?,?)",(uid,f'https://web.push.apple.com/{uid}','key','auth','now','now')).lastrowid

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

def test_bundled_once_only_for_child_and_persistent_across_restart(env):
    client,_,patch=setup(env);subscribe();subscribe(1)
    client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    patch.setattr(r,'snapshot',lambda *a:dict(homework=2,material=3,feedback=1))
    calls=[];patch.setattr(r,'send_push',lambda sub,payload,**kw:(calls.append((sub,payload,kw)) or (True,200)))
    r.run_once(NOW);db.init_webapp_db();r.run_once(NOW)
    assert len(calls)==1 and calls[0][0]['endpoint'].endswith('/2')
    assert calls[0][2]['ttl']==1800 and 'Hausaufgaben' in calls[0][1]['body'] and 'Fachmaterial' in calls[0][1]['body']
    assert client.get(URL).json()['last_delivery']['status']=='accepted'

def test_no_push_when_done_outside_window_disabled_or_source_unavailable(env):
    client,_,patch=setup(env);subscribe()
    client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    calls=[];patch.setattr(r,'send_push',lambda *a,**kw:calls.append(1))
    patch.setattr(r,'snapshot',lambda *a:dict(homework=0,material=0,feedback=0))
    r.run_once(NOW)
    patch.setattr(r,'snapshot',lambda *a:dict(homework=1,material=0,feedback=0))
    r.run_once(NOW.replace(hour=17));r.run_once(NOW.replace(hour=19));r.run_once(NOW.replace(hour=23))
    def broken(*a):raise RuntimeError('source missing')
    patch.setattr(r,'snapshot',broken);r.run_once(NOW)
    client.put(URL,json={'enabled':False});r.run_once(NOW)
    assert calls==[]
    assert client.get(URL).json()['last_delivery'] is None

def test_failed_push_not_replayed_and_dead_subscription_removed(env):
    client,_,patch=setup(env);subscribe();client.put(URL,json={'enabled':True,'remind_at':'18:00'})
    patch.setattr(r,'snapshot',lambda *a:dict(homework=0,material=1,feedback=0))
    calls=[];patch.setattr(r,'send_push',lambda *a,**kw:(calls.append(1) or (False,410)))
    r.run_once(NOW);r.run_once(NOW)
    assert calls==[1]
    assert client.get(URL).json()['last_delivery']['status']=='failed'
    assert client.get(URL).json()['devices']==0

def test_snapshot_uses_due_tasks_material_and_ended_feedback(env):
    _,_,patch=setup(env)
    def plan(account,day):
        if day==NOW.date():return [],'x',[dict(id=1,end_hhmm='10:00'),dict(id=2,end_hhmm='19:00'),dict(id=3,end_hhmm='11:00',is_cancelled=True)]
        return [dict(key='subject:math',label='Mathematik')],'x',[]
    patch.setattr(r,'packing_plan',plan)
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO tasks(account_id,title,status,source,due_date,created_at,updated_at) VALUES(1,'Aufgabe','open','manual','2026-09-15','now','now')")
    assert r.snapshot(1,NOW)==dict(homework=1,material=1,feedback=1)
    with closing(db.webapp_conn()) as c:
        c.execute("UPDATE tasks SET status='done'")
        c.execute("INSERT INTO packing_items VALUES(1,'2026-09-15','subject:math',1,1,'now',2)")
    assert r.snapshot(1,NOW)==dict(homework=0,material=0,feedback=1)

def test_subscription_rejects_non_provider_endpoints():
    for endpoint in ['http://localhost/push','https://127.0.0.1/push','https://web.push.apple.com.evil.test/push','https://user:pass@web.push.apple.com/push']:
        with pytest.raises(ValueError):SubscribeIn(endpoint=endpoint,keys={'p256dh':'key','auth':'auth'})
    assert SubscribeIn(endpoint='https://web.push.apple.com/a',keys={'p256dh':'key','auth':'auth'})


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
