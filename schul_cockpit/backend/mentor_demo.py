"""Synthetic mentor data: deliberately no archive, profile or learning-state reads."""
import json
from contextlib import closing
from .db import webapp_conn
from .learning import now_iso
from .mentor_context import fingerprint

TOPICS={'Deutsch':'Nominalisierte Adjektive erkennen', 'Mathematik':'Brüche auf einen gemeinsamen Nenner bringen', 'Geschichte':'Leben in einer mittelalterlichen Stadt'}

def snapshot():
    return dict(profile={'grade':6,'school_year':'Demo','ai_enabled':True,'daily_minutes':10,'study_days':'[0,1,2,3,4,5,6]','max_sessions':3}, enabled=True,background=False,lessons=[],errors=[],read_at=now_iso())

def context(account_id, session):
    with closing(webapp_conn()) as c:
        messages=[dict(r) for r in c.execute('SELECT role,text FROM mentor_messages WHERE session_id=? AND account_id=? ORDER BY id DESC LIMIT 8',(session['id'],account_id))][::-1]
    state=dict(mode='Demo mit erfundenen Beispieldaten; keine Aussagen über ein echtes Kind',grade=6,school_year='Demo',subject=session['subject'],goal=session['goal'],source={'synthetic':True},
               lessons=[{'text':TOPICS.get(session['subject'],session['goal']),'rating':2,'note':'Erfundene Rückmeldung: Ich verstehe das Beispiel noch nicht.'}],
               tasks=[],homework=[],previous=[],evidence=[],materials=[],errors=[],topic_connections=[])
    version=fingerprint(state)
    state.update(messages=messages,summary=session['summary'],phase=session['phase'],current_task=json.loads(session['current_task']) if session['current_task'] else None,help_count=session['help_count'],task_help=bool(session['task_help']),read_at=now_iso())
    return state,version,snapshot()
