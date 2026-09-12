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
    assert [x['subject'] for x in result.json()['candidates']]==['Deutsch']


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
        c.execute("INSERT INTO tasks(account_id,title,subject_name,status,source,created_at,updated_at,completed_at) VALUES(1,'Deutsch Hausaufgabe','Deutsch','done','manual','now','now','now')")
    r=send(client,s,kind='answer',text='Nach etwas ist es nominalisiert.');assert r.status_code==200,r.text;s=r.json()
    assert contexts[-1]['tasks'][0]['status']=='done'
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
        eid=c.execute("INSERT INTO mentor_exams(account_id,title,subject,scope_json,tasks_json,minutes,status,created_at) VALUES(1,'Probeklausur','Deutsch',?,?,15,'published','now')",(json.dumps({'topics':['Nominalisierung'],'confirmed':False}),json.dumps(tasks))).lastrowid
    child(state);base=B+'/exams';r=client.post(base+f'/{eid}/start');assert r.status_code==200,r.text;a=r.json()
    assert TASK['solution'] not in json.dumps(a)
    assert client.get(base+f'/{eid}/review').status_code==403
    assert client.post(base+f'/{eid}/start').json()['id']==a['id']
    with closing(db.webapp_conn()) as c:c.execute("UPDATE mentor_exams SET tasks_json='[]' WHERE id=?",(eid,))
    assert len(client.get(base+f"/attempts/{a['id']}").json()['exam']['tasks'])==3
    r=client.put(base+f"/attempts/{a['id']}",json={'version':0,'answers':{'0':'Mein Versuch'},'paused':True});assert r.status_code==200
    assert client.post(base+f"/attempts/{a['id']}/grade-next").status_code==409
    a=client.post(base+f"/attempts/{a['id']}/submit").json();assert a['status']=='submitted'
    mock(patch,[{'points':2,'rationale':'Teilweise erklärt.','next_step':'Begründung ergänzen.','uncertain':False}])
    for _ in range(3):
        r=client.post(base+f"/attempts/{a['id']}/grade-next");assert r.status_code==200,r.text
    assert r.json()['status']=='graded' and len(r.json()['feedback'])==3
    assert client.post(base+f"/attempts/{a['id']}/grade-next").status_code==200


def test_parent_test_run_does_not_create_child_evidence(setup):
    client,state,patch=setup
    mock(patch,[reply(),reply(task=None,action='finish',assessment={'result':'correct','rationale':'Passend.'})])
    s=start(client);assert s['is_test']==1
    s=send(client,s).json();r=send(client,s,kind='answer',text='Nominalisiert.')
    assert r.status_code==200,r.text
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT COUNT(*) FROM mentor_evidence').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM mentor_skills').fetchone()[0]==0
    child(state)
    assert client.get(B+f"/sessions/{s['id']}").status_code==404
    assert client.get(B).json()['sessions']==[]


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
