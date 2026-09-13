"""Packing persists across days/devices without inventing material or child performance."""
from contextlib import closing
from datetime import date
import sqlite3
from dataclasses import replace
import pytest
from test_learning import env, child
from backend import db, packing
from backend.routers import packing as routes

DAY = date(2026, 9, 14)

def install(env):
    client, state, patch = env
    client.app.include_router(routes.router, prefix='/api')
    child(state)
    lessons = [dict(subject_name='Mathematik'), dict(subject_name='Sport'), dict(subject_name='Mathematik')]
    patch.setattr(routes, 'today_local', lambda: DAY)
    patch.setattr(packing, 'lessons_for_date', lambda conn, account, day: lessons)
    patch.setattr(packing, 'hidden_keys', lambda account: set())
    patch.setattr(packing, 'lesson_is_hidden', lambda lesson, hidden: False)
    return client, state, patch, lessons

def url(day=DAY, account=1):
    return f'/api/accounts/{account}/packing/{day.isoformat()}'

def mark(client, data, item, done=True):
    return client.put(url(date.fromisoformat(data['school_day']), data['account_id']), json=dict(item_key=item['key'],done=done,revision=item['revision'],plan_key=data['plan_key']))

def test_general_items_dedup_and_saved_until_the_actual_school_day(env):
    client, _, patch, _ = install(env)
    result = client.get(url()).json()
    assert [i['label'] for i in result['items']] == ['Mathematik','Sport']
    assert len(result['schedule'])==3
    assert [r['material_checkbox'] for r in result['schedule']]==[True,True,False]
    for item in result['items']:
        response = mark(client, result, item)
        assert response.status_code == 200
    saved = client.get(url()).json()
    assert saved['status'] == 'packed'
    patch.setattr(routes, 'today_local', lambda: date(2026,9,15))
    assert client.get(url()).json() == saved
    assert client.get(url(date(2026,9,15))).json()['confirmed_count'] == 0
    db.init_webapp_db()
    assert client.get(url()).json() == saved

def test_changed_subjects_leave_only_new_items_open_and_reject_old_plan(env):
    client, _, _, lessons = install(env)
    old=client.get(url()).json()
    for item in old['items']: assert mark(client,old,item).status_code==200
    lessons[0]['room']='204'
    assert client.get(url()).json()['status']=='packed'
    lessons.append(dict(subject_name='Kunst'))
    updated=client.get(url()).json()
    assert updated['status']=='open' and updated['confirmed_count']==2
    assert [i['label'] for i in updated['items'] if not i['done']]==['Kunst']
    assert mark(client,old,old['items'][0]).status_code==409
    lessons[-1]['is_cancelled']=True
    assert client.get(url()).json()['status']=='packed'

def test_permissions_conflicts_and_corrections(env):
    client,state,_,_=install(env)
    data=client.get(url()).json(); item=data['items'][0]
    assert client.get(url(account=2)).status_code==403
    assert mark(client,data,item).status_code==200
    assert mark(client,data,item,False).status_code==409
    saved=client.get(url()).json(); updated=saved['items'][0]
    assert mark(client,saved,updated).json()['items'][0]['revision']==updated['revision']
    assert mark(client,saved,updated,False).json()['confirmed_count']==0
    state.user=replace(state.user,id=4,role='parent')
    assert client.get(url()).json()['can_write'] is False
    assert mark(client,data,item).status_code==403

def test_no_lesson_no_false_completion_and_data_failure_keeps_confirmations(env):
    client,_,patch,lessons=install(env)
    data=client.get(url()).json();assert mark(client,data,data['items'][0]).status_code==200
    def broken(*args):raise sqlite3.OperationalError('unavailable')
    patch.setattr(packing,'lessons_for_date',broken)
    assert client.get(url()).status_code==503
    patch.setattr(packing,'lessons_for_date',lambda *args: lessons)
    assert client.get(url()).json()['confirmed_count']==1
    for l in lessons:l['was_absent']=True
    result=client.get(url()).json()
    assert result['items']==[] and result['status']=='no_lessons'
    assert mark(client,data,data['items'][0]).status_code==409

def test_demo_and_invalid_input_cannot_change_state(env):
    client,_,_,_=install(env)
    data=client.get(url()).json();item=data['items'][0]
    body=dict(item_key=item['key'],done='yes',revision=0,plan_key=data['plan_key'])
    assert client.put(url(),json=body).status_code==422
    with closing(db.webapp_conn()) as c:c.execute('UPDATE users SET demo_mode=1 WHERE id=2')
    assert client.get(url()).json()['can_write'] is False
    assert mark(client,data,item).status_code==409


def test_timetable_retains_cancellations_changes_and_ignores_old_general_items(env):
    client,_,_,lessons=install(env)
    lessons[0].update(id=1,start_hhmm='08:00',end_hhmm='08:45',room='204',room_orig='102',is_room_substituted=True,teacher_name='Vertretung',teacher_orig_name='Stammlehrkraft',is_teacher_substituted=True)
    lessons.append(dict(id=4,subject_name='Physik',is_cancelled=True,start_hhmm='11:00',end_hhmm='11:45'))
    data=client.get(url()).json()
    assert len(data['schedule'])==4
    assert data['schedule'][0]['room_orig']=='102' and data['schedule'][0]['teacher_orig_name']=='Stammlehrkraft'
    assert data['schedule'][-1]['is_cancelled'] and data['schedule'][-1]['material_key'] is None
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO packing_items VALUES(1,?,'basic:drink',0,1,'now',2)",(DAY.isoformat(),))
    for item in data['items']:assert mark(client,data,item).status_code==200
    saved=client.get(url()).json()
    assert saved['status']=='packed' and saved['confirmed_count']==2
    assert not any(i['key'].startswith('basic:') for i in saved['items'])
