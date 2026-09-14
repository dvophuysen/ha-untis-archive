"""Meaningful mentor acceptance: ownership, continuity, help, costs, fixed exams."""
import json
import sqlite3
from contextlib import closing
from datetime import date
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_learning import env,seed,child,P,path
from backend import db,ai_gateway as ai,mentor_context as mc
from backend.routers import mentor as m,mentor_exams as ex

@pytest.fixture
def setup(env):
    client,state,patch=env
    client.app.include_router(m.router,prefix='/api');client.app.include_router(ex.router,prefix='/api')
    seed(client,ai_enabled=True,daily_minutes=30,max_sessions=3)
    patch.setattr(m,'now_iso',lambda:'2026-09-11T15:00:00+02:00')
    for mod in [m,mc,ai]:
        patch.setattr(mod,'today_local',lambda:date(2026,9,11)) if hasattr(mod,'today_local') else None
    patch.setitem(ai.RATES,'test',(10.,45.))
    for k,v in {'LEARNING_AI_MODEL':'test','LEARNING_AI_URL':'https://example.com/responses','LEARNING_AI_KEY':'fake'}.items():patch.setenv(k,v)
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.executescript("CREATE TABLE lessons(id INTEGER PRIMARY KEY,account_id INTEGER,date TEXT,start_time TEXT,end_time TEXT,subject_name TEXT,subject_untis_id INTEGER,teacher_untis_id INTEGER,lstext TEXT,was_absent INTEGER,code TEXT); INSERT INTO lessons VALUES(1,1,'2026-09-11','07:50','08:35','Deutsch',1,1,'Adjektive großschreiben',0,NULL);")
    yield client,state,patch

B=path()+'/mentor'
TASK={'prompt':'Erkläre die Schreibung von etwas Gutes.','solution':'Gutes ist nominalisiert.','criteria':'Begründung und Großschreibung.','skill_title':'Nominalisierung','objective':'Ich kann nominalisierte Adjektive erkennen.','operator':'Erkläre','afb':2}

def reply(task=TASK,assessment=None,action='task',**extra):
    return {'message':'Schauen wir ein Beispiel an.','choices':[],'action':action,'task':task,'assessment':assessment,'summary':'Nominalisierung wurde an einer Aufgabe begonnen.',**extra}


def start(client):
    r=client.post(B+'/sessions',json={'subject':'Deutsch','lesson_id':1})
    assert r.status_code==200,r.text
    return r.json()


def test_dashboard_tolerates_lessons_without_subject(setup):
    client,_,_=setup
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        for subject in (None,'','   '):
            c.execute("INSERT INTO lessons(account_id,date,subject_name,lstext) VALUES(1,'2026-09-11',?,'Allgemeine Veranstaltung')",(subject,))
    result=client.get(B)
    assert result.status_code==200,result.text
    assert {x['subject'] for x in result.json()['shared_plan']['goals']}=={'Deutsch'}


def test_discovered_connections_require_unchanged_lesson(setup):
    client,_,_=setup
    with closing(db.webapp_conn()) as c:
        t=c.execute('SELECT id,profile_id FROM learning_topics LIMIT 1').fetchone()
        c.execute('INSERT INTO learning_discovery_topics VALUES(?,?,?,?,?,?)',(t['id'],'Kurze Erklärung','Bildliche Brücke','Grundlage','Möglicher Ausblick','now'))
        c.execute('INSERT INTO learning_discovery_items(account_id,profile_id,lesson_id,fingerprint,topic_id,note) VALUES(?,?,?,?,?,?)',(1,t['profile_id'],1,mc.fingerprint(['2026-09-11','Deutsch','Adjektive großschreiben']),t['id'],''))
    s=mc.snapshot(1)
    assert mc.candidates(s)[0]['title']=='Argumentieren'
    session=start(client)
    with closing(db.webapp_conn()) as c: raw=dict(c.execute('SELECT * FROM mentor_sessions WHERE id=?',(session['id'],)).fetchone())
    ctx,_,_=mc.context(1,raw)
    assert ctx['topic_connections'][0]['bridge']=='Bildliche Brücke'
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:c.execute("UPDATE lessons SET lstext='Veränderter Stoff' WHERE id=1")
    ctx,_,_=mc.context(1,raw)
    assert ctx['topic_connections']==[]


def send(client,s,**args):
    key='request_'+str(s['version'])
    return client.post(B+f"/sessions/{s['id']}/turn",json={'request_key':key,'version':s['version'],'text':'Kurz ausprobieren',**args})


def mock(patch,outputs,contexts=None):
    async def complete(account,purpose,instruction,context,*args,**kw):
        if contexts is not None:contexts.append(context)
        out=outputs.pop(0) if len(outputs)>1 else outputs[0]
        return json.dumps(out),{},'fake'
    patch.setattr(ai,'complete',complete)


def test_persistent_context_help_and_delayed_evidence(setup):
    client,state,patch=setup;child(state)
    contexts=[]
    mock(patch,[reply(),reply(task=None,action='explain'),reply(task={**TASK,'prompt':'Warum schreibt man viel Neues groß?'},assessment={'result':'correct','rationale':'Regel passend erklärt.'})],contexts)
    s=start(client)
    assert 'solution' not in json.dumps(s)
    r=send(client,s);assert r.status_code==200,r.text;s=r.json()
    assert TASK['solution'] not in json.dumps(s)
    # Stored task survives another GET / fresh client request.
    assert client.get(B+f"/sessions/{s['id']}").json()['task']['prompt']==TASK['prompt']
    s=send(client,s,kind='hint',text='kp').json()
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO tasks(account_id,title,subject_name,status,source,created_at,updated_at,completed_at) VALUES(1,'Deutsch Hausaufgabe','DEUTSCH','done','manual','now','now','now')")
    r=send(client,s,kind='answer',text='Nach etwas ist es nominalisiert.');assert r.status_code==200,r.text;s=r.json()
    assert contexts[-1]['tasks'][0]['status']=='done'
    assert contexts[-1]['rating_meaning']['1']=='nicht verstanden'
    with closing(db.webapp_conn()) as c:
        evidence=c.execute('SELECT * FROM mentor_evidence').fetchone()
        assert evidence['help_used']==1 and evidence['result']=='correct'
    summary=client.get(B).json();assert summary['progress'][0]['independent']==0
    # Same message must not call model or create evidence twice.
    old={**s,'version':s['version']-1};assert send(client,old,kind='answer',text='Doppelter Klick').status_code==200
    assert client.post(B+f"/sessions/{s['id']}/turn",json={'request_key':'different','version':0,'text':'alt'}).status_code==409


def test_other_child_and_read_only_parent_cannot_mutate(setup):
    client,state,patch=setup;s=start(client)
    child(state,3)
    assert client.get(B+f"/sessions/{s['id']}").status_code==403
    assert client.get(path(2)+f"/mentor/sessions/{s['id']}").status_code==404
    assert client.put(B+'/budget-opening',json={'spent_eur':0}).status_code==403
    child(state)
    assert client.put(B+'/settings',json={'enabled':True}).status_code==403


def test_short_input_is_not_graded_and_finish_needs_no_model(setup):
    client,_,patch=setup;calls=[]
    mock(patch,[reply(assessment={'result':'incorrect','rationale':'Ungerechtfertigt.'})],calls)
    s=send(client,start(client)).json()
    r=send(client,s,text='kp',kind='answer');assert r.status_code==200,r.text;s=r.json()
    with closing(db.webapp_conn()) as c:assert c.execute('SELECT COUNT(*) FROM mentor_evidence').fetchone()[0]==0
    n=len(calls);r=send(client,s,kind='finish');assert r.json()['status']=='completed';assert len(calls)==n


def test_stale_source_rejected_without_learning_claim(setup):
    client,_,patch=setup
    async def changed(*args,**kw):
        with sqlite3.connect(db.SETTINGS.history_db_path) as c:c.execute("UPDATE lessons SET lstext='Anderer Unterricht' WHERE id=1")
        return json.dumps(reply()),{},'fake'
    patch.setattr(ai,'complete',changed)
    s=start(client);r=send(client,s);assert r.status_code==409
    saved=client.get(B+f"/sessions/{s['id']}").json();assert not saved['processing'] and saved['task'] is None


def test_budget_reservation_is_atomic_and_failures_stay_charged(setup):
    with closing(db.webapp_conn()) as c:
        ai.init_config(c);c.execute('UPDATE mentor_ai_config SET monthly_micro=150000 WHERE id=1')
    def reserve():
        try:return ai.reserve(1,'mentor',None,10000,1000)
        except Exception:return None
    with ThreadPoolExecutor(max_workers=2) as pool:keys=list(pool.map(lambda _:reserve(),range(2)))
    assert sum(k is not None for k in keys)==1
    key=next(k for k in keys if k);ai.settle(key,error='timeout')
    assert ai.status()['used_eur']==.145
    ai.settle(key,{'usage':{'input_tokens':1000,'output_tokens':100}})
    assert ai.status()['used_eur']==.0145


def test_unknown_model_and_prior_usage_fail_closed(setup):
    _,_,patch=setup
    patch.setenv('LEARNING_AI_MODEL','unknown')
    with pytest.raises(Exception):ai.reserve(1,'mentor',None,100,100)
    patch.setenv('LEARNING_AI_MODEL','test')
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO learning_ai_usage VALUES(1,'2026-09-01',2)")
    assert not ai.status()['opening_confirmed']
    with pytest.raises(Exception):ai.reserve(1,'mentor',None,100,100)


def test_absence_overlap_and_hidden_courses(setup):
    lesson={'date':'2026-09-11','start_time':'07:50','end_time':'08:35'}
    absences=[{'start_date':'2026-09-11','end_date':'2026-09-11','start_time':'07:50','end_time':'07:52'}]*2
    assert mc.missed_minutes(lesson,absences)==2
    with closing(db.webapp_conn()) as c:c.execute("INSERT INTO hidden_courses(account_id,course_key,created_at) VALUES(1,'1:1','now')")
    assert mc.snapshot(1)['lessons']==[]


def test_exam_fixed_version_secret_answers_and_resume(setup):
    client,state,patch=setup
    tasks=[{**TASK,'prompt':TASK['prompt']+str(i),'points':3,'minutes':5} for i in range(3)]
    with closing(db.webapp_conn()) as c:
        eid=c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) VALUES(1,'Probeklausur','Deutsch',?,?,15,'draft','now')",(json.dumps({'topics':['Nominalisierung'],'confirmed':False}),json.dumps(tasks))).lastrowid
    base=B+'/exams'
    edit={'title':'Geprüfte Probeklausur','tasks':tasks}
    assert client.put(base+f'/{eid}',json=edit).status_code==200
    assert client.post(base+f'/{eid}/publish',json={'reviewed':True}).status_code==200
    assert client.put(base+f'/{eid}',json=edit).status_code==409
    child(state)
    assert client.put(base+f'/{eid}',json=edit).status_code==403
    r=client.post(base+f'/{eid}/start');assert r.status_code==200,r.text;a=r.json()
    assert TASK['solution'] not in json.dumps(a)
    assert client.get(base+f'/{eid}/review').status_code==403
    assert client.post(base+f'/{eid}/start').json()['id']==a['id']
    with closing(db.webapp_conn()) as c:c.execute("UPDATE mentor_exams SET tasks_json='[]' WHERE id=?",(eid,))
    assert len(client.get(base+f"/attempts/{a['id']}").json()['exam']['tasks'])==3
    r=client.put(base+f"/attempts/{a['id']}",json={'version':0,'answers':{'0':'Mein Versuch'},'paused':True});assert r.status_code==200
    assert client.post(base+f"/attempts/{a['id']}/grade-next").status_code==409
    a=client.post(base+f"/attempts/{a['id']}/submit").json();assert a['status']=='submitted'
    mock(patch,[{'points':2.5,'rationale':'Teilweise erklärt.','next_step':'Begründung ergänzen.','uncertain':False}])
    for _ in range(3):
        r=client.post(base+f"/attempts/{a['id']}/grade-next");assert r.status_code==200,r.text
    assert r.json()['status']=='graded' and len(r.json()['feedback'])==3
    assert r.json()['feedback']['0']['points']==2.5
    assert client.post(base+f"/attempts/{a['id']}/grade-next").status_code==200


def test_parent_session_belongs_to_the_child_until_marked_as_test(setup):
    client,state,patch=setup;parent=state.user
    mock(patch,[reply(),reply(task=None,action='finish',assessment={'result':'correct','rationale':'Passend.'})])
    s=start(client);assert s['is_test']==0
    s=send(client,s).json();r=send(client,s,kind='answer',text='Nominalisiert.')
    assert r.status_code==200,r.text
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT COUNT(*) FROM mentor_evidence WHERE invalidated=0').fetchone()[0]==1
    # The child finds the shared verlauf on its own device, and sees who wrote.
    child(state)
    seen=client.get(B+f"/sessions/{s['id']}")
    assert seen.status_code==200,seen.text
    assert {x['author'] for x in seen.json()['messages'] if x['role']=='user'}=={'eltern'}
    assert [x['id'] for x in client.get(B).json()['sessions']]==[s['id']]
    # A pure tryout is taken out afterwards, never declared in advance.
    state.user=parent
    assert client.put(B+f"/sessions/{s['id']}/counts",json={'counts':False}).json()['is_test']==1
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT COUNT(*) FROM mentor_evidence WHERE invalidated=0').fetchone()[0]==0
    child(state)
    assert client.get(B+f"/sessions/{s['id']}").status_code==404
    assert client.get(B).json()['sessions']==[]


def test_homework_help_has_no_clock_and_survives_a_break(setup):
    client,state,patch=setup;child(state)
    with closing(db.webapp_conn()) as c:
        tid=c.execute("INSERT INTO tasks(account_id,title,subject_name,notes,source,created_at,updated_at) VALUES(1,'Lerne für den Test','Physik','Aufgabe 3','manual','now','now')").lastrowid
    s=client.post(B+'/sessions',json={'subject':'Physik','homework_task_id':tid}).json()
    # Neither the practice clock nor the turn cap may end an unfinished homework.
    with closing(db.webapp_conn()) as c:
        c.execute('UPDATE mentor_sessions SET turns=20,elapsed_seconds=?,active_since=NULL WHERE id=?',(s['max_minutes']*60+200,s['id']))
    mock(patch,[reply(task=None,action='clarify')])
    r=send(client,client.get(B+f"/sessions/{s['id']}").json(),text='Und wie geht I3?')
    assert r.status_code==200,r.text
    assert r.json()['status']=='active'
    # An interrupted homework is picked up again, never started from scratch.
    with closing(db.webapp_conn()) as c:c.execute("UPDATE mentor_sessions SET status='completed',phase='finished' WHERE id=?",(s['id'],))
    again=client.post(B+'/sessions',json={'subject':'Physik','homework_task_id':tid}).json()
    assert again['id']==s['id'] and again['status']=='active'
    assert len(again['messages'])>=3
    # An empty duplicate from an earlier break must not swallow the real one.
    with closing(db.webapp_conn()) as c:
        c.execute("INSERT INTO mentor_sessions(account_id,user_id,subject,goal,max_minutes,source_json,created_at,updated_at,is_test) SELECT account_id,user_id,subject,goal,max_minutes,source_json,created_at,updated_at,0 FROM mentor_sessions WHERE id=?",(s['id'],))
    assert client.post(B+'/sessions',json={'subject':'Physik','homework_task_id':tid}).json()['id']==s['id']


def test_finished_practice_session_can_be_picked_up_again(setup):
    client,state,patch=setup;child(state)
    s=start(client)
    with closing(db.webapp_conn()) as c:c.execute("UPDATE mentor_sessions SET status='completed',phase='finished' WHERE id=?",(s['id'],))
    assert send(client,client.get(B+f"/sessions/{s['id']}").json()).status_code==409
    back=client.post(B+f"/sessions/{s['id']}/resume")
    assert back.status_code==200,back.text
    assert back.json()['status']=='active'
    mock(patch,[reply()])
    assert send(client,back.json()).status_code==200


def test_photo_scope_and_unreadable_upload(setup):
    import io
    from PIL import Image
    client,state,patch=setup;child(state);s=start(client)
    assert client.post(B+f"/sessions/{s['id']}/photos",files={'file':('bad.jpg',b'not an image','image/jpeg')}).status_code==422
    out=io.BytesIO();Image.new('RGB',(32,32),'white').save(out,format='PNG')
    r=client.post(B+f"/sessions/{s['id']}/photos",files={'file':('test.png',out.getvalue(),'image/png')})
    assert r.status_code==200,r.text;aid=r.json()['id']
    assert client.get(B+f'/photos/{aid}').status_code==200
    child(state,3);assert client.get(path(2)+f'/mentor/photos/{aid}').status_code==404


def test_reported_usage_above_reservation_disables_new_calls(setup):
    key=ai.reserve(1,'mentor',None,100,256)
    ai.settle(key,{'usage':{'input_tokens':10000,'output_tokens':1000}})
    assert not ai.status()['opening_confirmed']
    with pytest.raises(Exception):ai.reserve(1,'mentor',None,100,256)


def test_time_and_turn_limits_close_without_model(setup):
    client,state,patch=setup;child(state);s=start(client)
    with closing(db.webapp_conn()) as c:c.execute('UPDATE mentor_sessions SET turns=12 WHERE id=?',(s['id'],))
    async def forbidden(*a,**kw):raise AssertionError('Limit must not call model')
    patch.setattr(ai,'complete',forbidden)
    assert send(client,s).json()['status']=='completed'


def test_demo_is_synthetic_persistent_and_excluded_from_live_learning(setup):
    client,state,patch=setup
    def no_real_data(*a,**kw):raise AssertionError('Demo accessed real lesson/profile context')
    patch.setattr(mc,'snapshot',no_real_data)
    contexts=[];mock(patch,[reply(),reply(assessment={'result':'correct','rationale':'Passend erklärt.'})],contexts)
    dashboard=client.get(B+'?demo=true')
    assert dashboard.status_code==200,dashboard.text
    assert dashboard.json()['profile']['school_year']=='Demo'
    assert client.post(B+'/sessions',json={'subject':'Deutsch','demo':True,'lesson_id':1}).status_code==422
    r=client.post(B+'/sessions',json={'subject':'Deutsch','demo':True})
    assert r.status_code==200,r.text
    s=r.json();assert s['is_demo']==s['is_test']==1
    s=send(client,s).json()
    result=send(client,s,kind='answer',text='Dies ist meine Dummy-Antwort.')
    assert result.status_code==200,result.text
    assert contexts[-1]['source']=={'synthetic':True}
    assert contexts[-1]['materials']==contexts[-1]['evidence']==contexts[-1]['previous']==[]
    assert 'Adjektive großschreiben' not in json.dumps(contexts)
    assert client.get(B+'?demo=true').json()['sessions'][0]['id']==s['id']
    with closing(db.webapp_conn()) as c:
        for table in ('mentor_skills','mentor_reviews','mentor_evidence'):
            assert c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0


def test_parents_write_along_while_demo_stays_out_of_the_child_view(setup):
    client,state,patch=setup;parent=state.user
    shared=start(client)
    demo=client.post(B+'/sessions',json={'subject':'Deutsch','demo':True}).json()
    child(state)
    assert client.get(B+f"/sessions/{demo['id']}").status_code==404
    assert client.get(B+'?demo=true').status_code==403
    assert client.post(B+'/sessions',json={'subject':'Deutsch','demo':True}).status_code==403
    # Same subject and goal: the child continues where the parent began.
    assert start(client)['id']==shared['id']
    assert [s['id'] for s in client.get(B).json()['sessions']]==[shared['id']]
    state.user=parent
    mock(patch,[reply()])
    live=client.get(B+f"/sessions/{shared['id']}").json()
    assert send(client,live,text='Schau mal hier.').status_code==200
    assert client.post(B+f"/sessions/{shared['id']}/pause",json={'paused':False}).status_code==200
    # Marked as a test it leaves the child's view, and it can be taken back.
    assert client.put(B+f"/sessions/{shared['id']}/counts",json={'counts':False}).status_code==200
    out=client.get(B).json()
    assert out['sessions']==[] and [s['id'] for s in out['legacy_sessions']]==[shared['id']]
    assert client.put(B+f"/sessions/{shared['id']}/counts",json={'counts':True}).status_code==200
    assert [s['id'] for s in client.get(B).json()['sessions']]==[shared['id']]
    assert client.put(B+f"/sessions/{demo['id']}/counts",json={'counts':True}).status_code==422
    child(state)
    assert client.put(B+f"/sessions/{shared['id']}/counts",json={'counts':False}).status_code==403


def test_demo_exam_never_publishes_to_child_and_parent_reads_real_attempt(setup):
    client,state,patch=setup;parent=state.user
    tasks=[{**TASK,'prompt':f'Erkläre Beispiel {i}','points':6,'minutes':5} for i in range(3)]
    contexts=[];mock(patch,[{'title':'Demo-Arbeit','tasks':tasks}],contexts)
    def no_real(*a,**kw):raise AssertionError('Demo exam accessed actual profile/lessons')
    original=mc.snapshot;patch.setattr(mc,'snapshot',no_real)
    r=client.post(B+'/exams',json={'subject':'Deutsch','scope':['Nominalisierung'],'minutes':15,'demo':True})
    assert r.status_code==200,r.text
    demo_id=r.json()['id'];assert contexts[-1]['materials']==contexts[-1]['lessons']==[]
    assert client.post(B+f'/exams/{demo_id}/publish',json={'reviewed':True}).status_code==200
    assert client.post(B+f'/exams/{demo_id}/start').status_code==200
    assert client.get(B+'/exams').json()['exams']==[]
    patch.setattr(mc,'snapshot',original)
    child(state)
    assert client.get(B+'/exams').json()=={'exams':[],'attempts':[]}
    assert client.post(B+f'/exams/{demo_id}/start').status_code==404
    assert client.get(B+'/exams?demo=true').status_code==403
    state.user=parent
    r=client.post(B+'/exams',json={'subject':'Deutsch','scope':['Nominalisierung'],'minutes':15})
    real_id=r.json()['id'];client.post(B+f'/exams/{real_id}/publish',json={'reviewed':True})
    child(state);a=client.post(B+f'/exams/{real_id}/start').json()
    a=client.put(B+f"/exams/attempts/{a['id']}",json={'version':a['version'],'answers':{'0':'Meine echte Antwort'},'paused':True}).json()
    state.user=parent
    assert [r['id'] for r in client.get(B+'/exams').json()['attempts']]==[a['id']]
    before=client.get(B+f"/exams/attempts/{a['id']}").json()
    assert before['read_only'] and before['answers']['0']=='Meine echte Antwort'
    assert client.put(B+f"/exams/attempts/{a['id']}",json={'version':a['version'],'answers':{'0':'Fälschung'}}).status_code==404
    assert client.post(B+f"/exams/attempts/{a['id']}/submit").status_code==404
    assert client.post(B+f"/exams/attempts/{a['id']}/grade-next").status_code==404
    assert client.get(B+f"/exams/attempts/{a['id']}/photos").status_code==200
    assert client.get(B+f"/exams/attempts/{a['id']}").json()==before


def test_scope_covers_all_lessons_and_homework_cached_and_used_for_exam(setup):
    from backend import exam_scope as es
    client,state,patch=setup;patch.setattr(es,'today_local',lambda:date(2026,9,11))
    original=es.snapshot
    def school(account,demo):
        s=original(account,demo)
        s['lessons']=[dict(id=i,date='2026-09-10',subject_name='Deutsch',text=f'Teilthema {i}',future=False,missed_minutes=45 if i==14 else 0) for i in range(15)]
        s['lessons'].append(dict(id=50,date='2026-09-10',subject_name='Deutsch',text='',future=False))
        s['homework']=[{'id':1,'subject_name':'DEUTSCH','assigned_date':'2026-09-10','due_date':'2026-09-12','text':'Festigung des ersten Themas'}]
        return s
    patch.setattr(es,'snapshot',school)
    contexts=[]
    async def model(account,purpose,instruction,ctx,*args,**kw):
        contexts.append((purpose,ctx))
        if purpose=='exam_scope':return json.dumps({'groups':[{'title':'Sprachwissen','category':'learning','detail':'Alle Teilthemen einschließlich Festigung','ids':[x['id'] for x in ctx['items']]}]}),{},'fake'
        return json.dumps({'title':'Stoffübersicht üben','tasks':[{**TASK,'skill_title':'Sprachwissen','prompt':f'Erkläre Teilthema {i}','minutes':5,'points':4} for i in range(3)]}),{},'fake'
    patch.setattr(ai,'complete',model)
    result=client.post(B+'/exams/scope',json={'subject':'Deutsch'})
    assert result.status_code==200,result.text
    plan=result.json();assert plan['lesson_count']==15 and plan['missing']==1
    assert len(plan['groups'][0]['sources'])==16 and plan['warnings']
    n=len(contexts);assert client.post(B+'/exams/scope',json={'subject':'Deutsch'}).json()['cached'];assert len(contexts)==n
    made=client.post(B+'/exams',json={'subject':'Deutsch','scope':['Sprachwissen'],'minutes':15,'scope_plan_id':plan['plan_id'],'selected_groups':[{'group_id':0,'title':'Sprachwissen'}]})
    assert made.status_code==200,made.text
    assert contexts[-1][1]['curriculum']['groups'][0]['detail']=='Alle Teilthemen einschließlich Festigung'
    assert contexts[-1][1]['lessons']==[]
    saved=client.get(B+f"/exams/{made.json()['id']}/review").json()
    assert len(saved['scope']['curriculum']['groups'][0]['sources'])==16
    assert client.post(B+'/exams',json={'subject':'Mathematik','scope':['Sprachwissen'],'minutes':15,'scope_plan_id':plan['plan_id'],'selected_groups':[{'group_id':0,'title':'Sprachwissen'}]}).status_code==422


def test_scope_rejects_incomplete_grouping_and_demo_never_reads_real(setup):
    from backend import exam_scope as es
    client,state,patch=setup;patch.setattr(es,'today_local',lambda:date(2026,9,11))
    def forbidden(*a,**k):raise AssertionError('Demo read real archive')
    patch.setattr(mc,'snapshot',forbidden)
    mock(patch,[{'groups':[{'title':'Ein Thema','category':'learning','detail':'Beschreibung','ids':[999]}]}])
    r=client.post(B+'/exams/scope',json={'subject':'Deutsch','demo':True})
    assert r.status_code==502,r.text
    mock(patch,[{'groups':[{'title':'Adjektive','category':'learning','detail':'Nominalisierung','ids':list(range(8))}]}])
    r=client.post(B+'/exams/scope',json={'subject':'Deutsch','demo':True})
    assert r.status_code==200,r.text
    assert r.json()['groups'][0]['sources'][0]['id']<0
    child(state);assert client.post(B+'/exams/scope',json={'subject':'Deutsch','demo':True}).status_code==403


def test_scope_last_exam_and_calendar_failure_are_explicit(setup):
    from backend import exam_scope as es
    client,state,patch=setup;patch.setattr(es,'today_local',lambda:date(2026,9,11))
    async def calendar(*a,**k):return {'exams':[{'date':'2026-09-09','subject_name':'DEUTSCH'}],'calendar_error':None}
    patch.setattr(es,'resolve_exams',calendar)
    mock(patch,[{'groups':[{'title':'Adjektive','category':'learning','detail':'Nominalisierung','ids':[0]}]}])
    r=client.post(B+'/exams/scope',json={'subject':'Deutsch','period':'last_exam'})
    assert r.status_code==200,r.text
    assert r.json()['start_date']=='2026-09-10'
    async def broken(*a,**k):return {'exams':[],'calendar_error':'offline'}
    patch.setattr(es,'resolve_exams',broken)
    assert client.post(B+'/exams/scope',json={'subject':'Deutsch','period':'last_exam'}).status_code==409


def test_print_is_solution_free_escaped_and_self_check_creates_no_score(setup):
    client,state,patch=setup
    tasks=[{**TASK,'prompt':'Nenne <script>alert(1)</script>','solution':'GEHEIME MUSTERLOESUNG','points':6,'minutes':5}]*3
    with closing(db.webapp_conn()) as c:
        eid=c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) VALUES(1,'Drucktest','Deutsch',?,?,15,'published','now')",(json.dumps({'topics':['Nominalisierung']}),json.dumps(tasks))).lastrowid
    child(state)
    r=client.get(B+f'/exams/{eid}/print')
    assert r.status_code==200 and 'text/html' in r.headers['content-type']
    assert 'GEHEIME MUSTERLOESUNG' not in r.text and '<script>alert' not in r.text and '&lt;script&gt;' in r.text
    assert 'window.print()' in r.text
    check=client.post(B+f'/exams/{eid}/self-check').json()
    assert check['self_check'] and check['tasks'][0]['solution']=='GEHEIME MUSTERLOESUNG'
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT COUNT(*) FROM mentor_exam_attempts').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM mentor_evidence').fetchone()[0]==0
        c.execute('UPDATE mentor_exams SET is_demo=1 WHERE id=?',(eid,))
    assert client.get(B+f'/exams/{eid}/print').status_code==404
    assert client.post(B+f'/exams/{eid}/self-check').status_code==404


def test_known_solutions_are_not_independent_evidence(setup):
    client,state,patch=setup
    tasks=[{**TASK,'prompt':f'Aufgabe {i}','points':6,'minutes':5} for i in range(3)]
    with closing(db.webapp_conn()) as c:
        eid=c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) VALUES(1,'Kontrolle','Deutsch',?,?,15,'published','now')",(json.dumps({'topics':['Nominalisierung']}),json.dumps(tasks))).lastrowid
    child(state)
    assert client.post(B+f'/exams/{eid}/self-check').status_code==200
    attempt=client.post(B+f'/exams/{eid}/start').json()
    client.put(B+f"/exams/attempts/{attempt['id']}",json={'version':0,'answers':{'0':'Richtige Antwort'}})
    client.post(B+f"/exams/attempts/{attempt['id']}/submit")
    mock(patch,[{'points':6,'rationale':'Richtig erklärt.','next_step':'Später erneut prüfen.','uncertain':False}])
    graded=client.post(B+f"/exams/attempts/{attempt['id']}/grade-next")
    assert graded.status_code==200,graded.text
    assert graded.json()['feedback']['0']['solution_seen']
    with closing(db.webapp_conn()) as c:assert c.execute('SELECT help_used FROM mentor_evidence').fetchone()[0]==1


def test_scope_merges_batches_without_losing_sources(setup):
    from backend import exam_scope as es
    client,_,patch=setup;patch.setattr(es,'today_local',lambda:date(2026,9,11))
    original=es.snapshot
    def school(account,demo):
        s=original(account,demo)
        s['lessons']=[dict(id=i,date='2026-09-10',subject_name='Deutsch',text=f'Thema {i}',future=False) for i in range(45)]
        return s
    patch.setattr(es,'snapshot',school)
    calls=[]
    async def model(account,purpose,instruction,ctx,*args,**kw):
        calls.append(ctx)
        return json.dumps({'groups':[{'title':'Zusammengehörige Themen','category':'learning','detail':'Alle Teilthemen im Zeitraum','ids':[x['id'] for x in ctx['items']]}]}),{},'fake'
    patch.setattr(ai,'complete',model)
    r=client.post(B+'/exams/scope',json={'subject':'Deutsch'})
    assert r.status_code==200,r.text
    assert len(calls)==3
    assert len(r.json()['groups'])==1
    assert {x['id'] for x in r.json()['groups'][0]['sources']}==set(range(45))


def test_unclear_scope_cannot_become_automatic_exam_content(setup):
    from backend import exam_scope as es
    client,_,patch=setup;patch.setattr(es,'today_local',lambda:date(2026,9,11))
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:c.execute("UPDATE lessons SET lstext='Vertretung: Aufgaben nach Vorgabe bearbeiten' WHERE id=1")
    mock(patch,[{'groups':[{'category':'unclear','title':'Unbekannte Aufgaben','detail':'Originalmaterial fehlt','ids':[0]}]}])
    plan=client.post(B+'/exams/scope',json={'subject':'Deutsch'}).json()
    assert plan['groups'][0]['category']=='unclear'
    result=client.post(B+'/exams',json={'subject':'Deutsch','scope':['Unbekannte Aufgaben'],'minutes':15,'scope_plan_id':plan['plan_id'],'selected_groups':[{'group_id':0,'title':'Unbekannte Aufgaben'}]})
    assert result.status_code==422,result.text


def test_child_can_generate_test_without_calendar_and_without_solution_leak(setup):
    client,state,patch=setup;child(state)
    tasks=[{**TASK,'prompt':f'Erkläre Beispiel {i}','minutes':5,'points':4} for i in range(3)]
    mock(patch,[{'title':'Mein Übungstest','tasks':tasks}])
    result=client.post(B+'/exams',json={'subject':'Physik','scope':['Nominalisierung'],'minutes':15})
    assert result.status_code==200,result.text
    eid=result.json()['id']
    row=client.get(B+'/exams').json()['exams'][0]
    assert row['status']=='published' and row['scope']['child_created'] and not row['scope']['parent_reviewed']
    assert TASK['solution'] not in json.dumps(row)
    assert client.get(B+f'/exams/{eid}/review').status_code==403
    attempt=client.post(B+f'/exams/{eid}/start')
    assert attempt.status_code==200 and TASK['solution'] not in attempt.text
    assert client.post(B+'/exams',json={'subject':'Physik','scope':['Nominalisierung'],'minutes':15,'demo':True}).status_code==403
    assert client.post(B+'/exams/scope',json={'subject':'Physik','demo':True}).status_code==403


def test_remove_session_deletes_evidence_and_time_but_preserves_other_work_and_costs(setup):
    client,state,patch=setup;parent=state.user;child(state)
    mock(patch,[reply(),reply(task=None,action='finish',assessment={'result':'correct','rationale':'Passend begründet.'})])
    s=start(client);s=send(client,s).json();s=send(client,s,kind='answer',text='Die Regel passt.').json()
    sid=s['id'];endpoint=B+f'/sessions/{sid}'
    assert client.request('DELETE',endpoint,json={'version':s['version']}).status_code==403
    state.user=parent
    with closing(db.webapp_conn()) as c:
        skill=c.execute('SELECT skill_id FROM mentor_evidence WHERE session_id=?',(sid,)).fetchone()[0]
        other=c.execute("INSERT INTO mentor_sessions(account_id,user_id,subject,goal,created_at,updated_at) VALUES(2,3,'Deutsch','Andere Einheit','now','now')").lastrowid
    assert client.request('DELETE',endpoint,json={'version':0}).status_code==409
    assert client.request('DELETE',endpoint,json={'version':s['version']}).status_code==200
    with closing(db.webapp_conn()) as c:
        for table in ('mentor_evidence','mentor_messages','mentor_attachments','learning_plan_blocks'):
            assert c.execute(f'SELECT COUNT(*) FROM {table} WHERE session_id=?',(sid,)).fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM mentor_sessions WHERE id=?',(other,)).fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM mentor_reviews WHERE skill_id=?',(skill,)).fetchone()[0]==0
        assert c.execute('SELECT 1 FROM learning_skill_state WHERE skill_id=?',(skill,)).fetchone() is None
        assert c.execute('SELECT 1 FROM mentor_skills WHERE id=?',(skill,)).fetchone() is None
        assert c.execute('SELECT 1 FROM learning_plan_links WHERE skill_id=?',(skill,)).fetchone() is None
    assert client.request('DELETE',endpoint,json={'version':s['version']}).status_code==404


def test_free_topic_does_not_reopen_an_unrelated_active_session(setup):
    client,state,_=setup;child(state)
    first=client.post(B+'/sessions',json={'subject':'Deutsch','goal':'Rechtschreibung','voluntary':True}).json()
    second=client.post(B+'/sessions',json={'subject':'Deutsch','goal':'Argumentieren','voluntary':True}).json()
    assert first['id']!=second['id'] and second['goal']=='Argumentieren'
    assert client.get(B+f"/sessions/{first['id']}").status_code==200
    again=client.post(B+'/sessions',json={'subject':'Deutsch','goal':'Argumentieren','voluntary':True}).json()
    assert again['id']==second['id']


def test_homework_help_is_scoped_current_and_not_a_practice_or_completion(setup):
    from backend import learning_plan as lp
    client,state,patch=setup;child(state)
    with closing(db.webapp_conn()) as c:
        tid=c.execute("INSERT INTO tasks(account_id,title,subject_name,notes,source,created_at,updated_at) VALUES(1,'Aufgabe 4','Deutsch','Erkläre den Arbeitsauftrag','manual','now','now')").lastrowid
        other=c.execute("INSERT INTO tasks(account_id,title,source,created_at,updated_at) VALUES(2,'Privat','manual','now','now')").lastrowid
        before=lp.usage(c,1,date(2026,9,11))
    payload={'subject':'untrusted','homework_task_id':tid}
    result=client.post(B+'/sessions',json=payload)
    assert result.status_code==200,result.text
    s=result.json();assert s['subject']=='Deutsch' and s['mode']=='homework_help'
    assert client.post(B+'/sessions',json=payload).json()['id']==s['id']
    assert client.post(B+'/sessions',json={**payload,'homework_task_id':other}).status_code==404
    assert client.post(B+'/sessions',json={**payload,'lesson_id':1}).status_code==422
    captured=[]
    async def complete(account,purpose,instruction,context,*args,**kw):
        assert instruction==m.HOMEWORK_INSTRUCTION+json.dumps(m.Reply.model_json_schema())
        captured.append(context)
        # Even an unwanted generated exercise cannot create mastery evidence.
        return json.dumps(reply(assessment={'result':'correct','rationale':'Test'})),{},'fake'
    patch.setattr(ai,'complete',complete)
    r=send(client,s,text='Was soll ich hier machen?')
    assert r.status_code==200,r.text
    assert r.json()['task'] is None
    assert captured[0]['source']['task']['id']==tid
    with closing(db.webapp_conn()) as c:
        assert lp.usage(c,1,date(2026,9,11))==before
        assert c.execute('SELECT COUNT(*) FROM mentor_evidence WHERE session_id=?',(s['id'],)).fetchone()[0]==0
        assert c.execute('SELECT status FROM tasks WHERE id=?',(tid,)).fetchone()[0]=='open'
        c.execute("UPDATE tasks SET notes='Neuer Arbeitsauftrag' WHERE id=?",(tid,))
    r=send(client,r.json(),text='Hilf mir beim ersten Schritt')
    assert r.status_code==200,r.text
    assert captured[-1]['source']['task']['notes']=='Neuer Arbeitsauftrag'


def test_old_empty_skills_do_not_appear_as_progress_or_review(setup):
    client,state,patch=setup;child(state)
    with closing(db.webapp_conn()) as c:
        skill=c.execute("INSERT INTO mentor_skills(account_id,subject,title,objective,source_json,created_at,updated_at) VALUES(1,'Deutsch','Alter Test','Test','{}','2026-09-01','2026-09-01')").lastrowid
    response=client.get(B)
    assert response.status_code==200,response.text
    assert not any(p['id']==skill for p in response.json()['progress'])
    assert not any(skill in g.get('skill_ids',[]) for g in response.json()['shared_plan']['goals'])


def test_deleting_one_session_keeps_another_sessions_skill_and_evidence(setup):
    client,state,patch=setup;parent=state.user;child(state)
    mock(patch,[reply(),reply(task=None,action='finish',assessment={'result':'correct','rationale':'Begründet.'})])
    s=start(client);s=send(client,s).json();s=send(client,s,kind='answer',text='Die Regel passt.').json()
    with closing(db.webapp_conn()) as c:
        skill=c.execute('SELECT skill_id FROM mentor_evidence WHERE session_id=?',(s['id'],)).fetchone()[0]
        other=c.execute("INSERT INTO mentor_sessions(account_id,user_id,skill_id,subject,goal,created_at,updated_at) VALUES(1,2,?,'Deutsch','Weitere Übung','2026-09-11','2026-09-11')",(skill,)).lastrowid
    state.user=parent
    assert client.request('DELETE',B+f'/sessions/{other}',json={'version':0}).status_code==200
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT 1 FROM mentor_skills WHERE id=?',(skill,)).fetchone()
        assert c.execute('SELECT COUNT(*) FROM mentor_evidence WHERE skill_id=?',(skill,)).fetchone()[0]==1
    assert any(p['id']==skill for p in client.get(B).json()['progress'])


def test_homework_chat_stays_open_until_the_task_is_ticked(setup):
    client,state,patch=setup;child(state)
    with closing(db.webapp_conn()) as c:
        tid=c.execute("INSERT INTO tasks(account_id,title,subject_name,source,created_at,updated_at) VALUES(1,'Latein Nr. 3','Latein','manual','now','now')").lastrowid
    s=client.post(B+'/sessions',json={'subject':'Latein','homework_task_id':tid}).json()
    # Neither "done for today" nor the mentor's own finish may close it.
    r=send(client,s,kind='finish')
    assert r.status_code==200,r.text
    assert r.json()['status']=='active' and r.json()['task_done'] is False
    mock(patch,[reply(task=None,action='finish')])
    r=send(client,client.get(B+f"/sessions/{s['id']}").json(),text='Und der Rest?')
    assert r.status_code==200,r.text
    assert r.json()['status']=='active'
    assert [x['id'] for x in client.get(B).json()['sessions']]==[s['id']]
    # The tick on the homework files it away; removing the tick brings it back.
    with closing(db.webapp_conn()) as c:c.execute("UPDATE tasks SET status='done' WHERE id=?",(tid,))
    listed={x['id']:x for x in client.get(B).json()['sessions']}
    assert listed[s['id']]['task_done'] is True
    assert client.get(B+f"/sessions/{s['id']}").json()['task_done'] is True
    with closing(db.webapp_conn()) as c:c.execute("UPDATE tasks SET status='open' WHERE id=?",(tid,))
    assert client.get(B).json()['sessions'][0]['task_done'] is False


def test_a_practice_unit_may_still_be_closed_by_the_mentor(setup):
    client,state,patch=setup;child(state)
    mock(patch,[reply(task=None,action='finish')])
    s=start(client)
    assert send(client,s).json()['status']=='completed'
