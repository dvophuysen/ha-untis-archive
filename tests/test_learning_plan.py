"""Shared state and bounded planning, tested against real API transactions."""
from datetime import date
from contextlib import closing
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import json
import sqlite3
from test_mentor import setup, start, send, mock, reply, TASK, B
from test_learning import env, child, seed, path
from backend import db, learning_plan as lp, mentor_context as mc
from backend.routers import plan as pr, afternoon, oral


def event(day, result='correct', help_used=0, variant=None, invalidated=0):
    return dict(created_at=day+'T15:00:00+02:00',result=result,help_used=help_used,variant_hash=variant or day,rationale='Kriterien geprüft',invalidated=invalidated)


def test_replay_spacing_errors_help_and_invalidated():
    evidence=[event('2026-09-01'),event('2026-09-01',variant='other')]
    r=lp.replay(evidence);assert r['level']==1 and r['due_date']=='2026-09-03'
    evidence += [event('2026-09-03'),event('2026-09-10')]
    r=lp.replay(evidence);assert r['level']==3 and r['due_date']=='2026-09-24'
    assert 'Mit Abstand' in r['label']
    wrong=event('2026-09-24','incorrect');r=lp.replay(evidence+[wrong]);assert r['level']==2 and r['due_date']=='2026-09-26'
    assert lp.replay(evidence+[event('2026-09-24',help_used=1)])['level']==3
    assert lp.replay(evidence+[event('2026-09-24','uncertain')])['level']==3
    wrong['invalidated']=1;assert lp.replay(evidence+[wrong])['due_date']=='2026-09-24'
    assert lp.replay([event('2026-09-01'),event('2026-09-20',variant='2026-09-01')])['level']==1


def install(client):
    for router in (pr.router,afternoon.router,oral.router):client.app.include_router(router,prefix='/api')


def test_shared_plan_budget_weekend_positive_rotation_and_duplicate_sources(setup):
    client,state,patch=setup;install(client)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("UPDATE lessons SET date='2026-09-08'")
        c.execute("INSERT INTO lessons VALUES(2,1,'2026-09-08','08:35','09:20','Deutsch',1,1,'Adjektive großschreiben',0,NULL)")
        c.execute("INSERT INTO lessons VALUES(3,1,'2026-09-08','09:45','10:30','Geschichte',2,1,'Grundherrschaft erklären',0,NULL)")
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,1,2,2,'now','now'),(1,3,2,3,'now','now')")
    plan=client.get('/api/accounts/1/plan').json()
    german=[g for g in plan['goals'] if g['kind']=='lesson' and g['subject']=='Deutsch']
    assert len(german)==1 and len(german[0]['sources'])==2
    assert len(plan['week'])==7
    assert any(g['subject']=='Geschichte' for g in plan['today']['actions'])
    assert not plan['week'][1]['actions'] # Saturday, unselected.
    after=client.get('/api/accounts/1/afternoon-plan').json()
    assert [g['goal_key'] for g in after['free_learning']]==[g['key'] for g in plan['today']['actions']]
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO tasks(account_id,title,status,source,estimated_minutes,created_at,updated_at,completed_at) VALUES(1,'Erledigte Hausaufgabe','done','manual',60,'now','now','2026-09-11T12:00:00')")
    plan=client.get('/api/accounts/1/plan').json()
    assert plan['today']['actions']==[] and plan['today']['used_minutes']==60
    assert plan['deferred']
    assert plan['today']['overload_minutes']==0 # Completed work is not pending homework.


def test_source_link_roundtrip_help_invalidation_and_parent_isolation(setup):
    client,state,patch=setup;install(client)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:c.execute("UPDATE lessons SET date='2026-09-08'")
    p=client.get('/api/accounts/1/plan').json();g=next(g for g in p['goals'] if g['kind']=='lesson')
    parent=state.user
    # Parent tests cannot create actual reservations or evidence.
    s=client.post(B+'/sessions',json=dict(subject=g['subject'],lesson_id=1,goal_key=g['key'])).json()
    with closing(db.webapp_conn()) as c:assert not c.execute('SELECT * FROM learning_plan_blocks').fetchall()
    child(state)
    mock(patch,[reply(),reply(task=None,action='finish',assessment=dict(result='correct',rationale='Regel passend erklärt.'))])
    s=client.post(B+'/sessions',json=dict(subject=g['subject'],lesson_id=1,goal_key=g['key'])).json()
    s=send(client,s).json();s=send(client,s,kind='answer',text='Nach etwas wird das Adjektiv nominalisiert.').json()
    p=client.get('/api/accounts/1/plan').json();g2=next(x for x in p['goals'] if x['key']==g['key'])
    assert g2['skill_ids'] and g2['session_id']==s['id'] and 'Selbstständig' in g2['state']
    assert not any(x['key']==g['key'] for x in p['today']['actions'])
    assert p['today']['used_minutes']==s['max_minutes']
    state.user=parent
    with closing(db.webapp_conn()) as c:eid=c.execute('SELECT id FROM mentor_evidence').fetchone()[0]
    assert client.post(B+f'/evidence/{eid}/invalidate',json={'reason':'Musterlösung war nicht zutreffend.'}).status_code==200
    p=client.get('/api/accounts/1/plan').json();g3=next(x for x in p['goals'] if x['key']==g['key'])
    assert 'Selbstständig gezeigt' not in g3['state']
    assert client.get('/api/accounts/2/plan').status_code==200
    child(state);assert client.get('/api/accounts/2/plan').status_code==403


def test_demo_history_contains_multiple_weeks_and_homework_without_real_access(setup):
    from backend import exam_scope as es
    client,state,patch=setup
    patch.setattr(mc,'snapshot',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('Real archive accessed')))
    async def group(account,purpose,instruction,context,*args,**kwargs):
        items=context['items']
        # Preserve every source in a representative three-topic model response.
        return json.dumps({'groups':[dict(category='learning',title='Frühmittelalter',detail='Franken und Sachsenkriege',ids=[0,1,2,9]),dict(category='learning',title='Grundherrschaft',detail='Leben auf dem Land',ids=[3,4,5,10]),dict(category='learning',title='Stadtleben',detail='Märkte und Zünfte',ids=[6,7,8,11])]}),{},'fake'
    patch.setattr(es.ai,'complete',group)
    r=client.post(B+'/exams/scope',json={'subject':'Geschichte','demo':True})
    assert r.status_code==200,r.text
    p=r.json();assert p['lesson_count']==9 and len(p['groups'])==3
    sources=[x for g in p['groups'] for x in g['sources']]
    assert len([x for x in sources if x['kind']=='homework'])==3
    assert any(x.get('missed_minutes')==45 for x in sources)
    assert client.post(B+'/exams/scope',json={'subject':'Geschichte','demo':True}).json()['cached']


def test_day_load_changes_proposal_and_voluntary_start_is_explicit(setup):
    client,state,patch=setup;install(client)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:c.execute("UPDATE lessons SET date='2026-09-08'")
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO lesson_checkins(account_id,lesson_id,user_id,rating,created_at,updated_at) VALUES(1,1,2,1,'now','now')")
    normal=client.get('/api/accounts/1/plan').json()
    busy=client.put('/api/accounts/1/plan/day',json={'load':'busy'}).json()
    assert sum(g['minutes'] for g in busy['today']['actions'])<=5
    assert busy['today']['planned_minutes']<normal['today']['planned_minutes']
    room=client.put('/api/accounts/1/plan/day',json={'load':'room'}).json()
    assert room['today']['planned_minutes']>busy['today']['planned_minutes']
    assert client.get('/api/accounts/1/plan').json()['today']['day_load']=='room'
    child(state)
    assert client.put('/api/accounts/2/plan/day',json={'load':'busy'}).status_code==403
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO tasks(account_id,title,status,source,estimated_minutes,created_at,updated_at,completed_at) VALUES(1,'Erledigte Hausaufgabe','done','manual',180,'now','now','2026-09-11T12:00:00')")
    client.put('/api/accounts/1/plan/day',json={'load':'normal'})
    assert client.post(B+'/sessions',json={'subject':'Deutsch','lesson_id':1}).status_code==409
    r=client.post(B+'/sessions',json={'subject':'Deutsch','lesson_id':1,'voluntary':True,'minutes':5})
    assert r.status_code==200,r.text
    assert r.json()['max_minutes']==5


def test_week_rotates_verified_topics_and_refreshes_lesson_dates(setup):
    client,state,patch=setup;install(client)
    snapshot=mc.snapshot(1)
    base=snapshot['lessons'][0]
    lessons=[]
    for i in range(6):
        lessons.append({**base,'id':100+i,'date':f'2026-09-{i+1:02d}','future':False,'text':f'German lesson {i}','subject_name':'Deutsch','rating':2,'topic':{'id':10,'title':'Grammatik'}})
    lessons += [{**base,'id':200,'date':'2026-09-01','future':False,'text':'Stadtleben','subject_name':'Geschichte','rating':2,'topic':{'id':11,'title':'Stadtleben'}},
                {**base,'id':201,'date':'2026-09-14','future':True,'subject_name':'Deutsch'},
                {**base,'id':202,'date':'2026-09-17','future':True,'subject_name':'Deutsch'}]
    snapshot['lessons']=lessons
    snapshot['profile']['study_days']='[0,1,2,3,4,5,6]'
    patch.setattr(lp,'envelope',lambda *a,**kw:(15,{'source':'test'},True))
    result=lp.build(1,snapshot=snapshot)
    actions=[g for d in result['week'] for g in d['actions']]
    assert len([g for g in actions if g.get('topic_id')==10])==1
    assert any(g['subject']=='Geschichte' for g in actions)
    assert len([g for g in result['goals'] if g.get('topic_id')==10])==6 # No mastery merge.
    assert all(not g['next_lesson'] or g['next_lesson']>=g['planned_date'] for g in actions)
