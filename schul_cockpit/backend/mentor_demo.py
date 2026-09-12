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

# A small multi-week curriculum makes grouping, homework and absence flows testable.
DEMO_UNITS = {
 'Geschichte': [
  ('Frühes Mittelalter', 'Das Frankenreich nach dem Ende des Weströmischen Reiches'),
  ('Frühes Mittelalter', 'Karl der Große: Herrschaft und Verwaltung des Frankenreiches'),
  ('Frühes Mittelalter', 'Die Sachsenkriege: Ursachen, Verlauf und Folgen'),
  ('Leben auf dem Land', 'Grundherrschaft: Aufgaben, Abgaben und Abhängigkeit der Bauern'),
  ('Leben auf dem Land', 'Alltag der Bauern und Dreifelderwirtschaft'),
  ('Leben auf dem Land', 'Vergleich: Leben auf dem Land damals und heute'),
  ('Die mittelalterliche Stadt', 'Stadtentstehung: Markt, Mauern und Stadtrecht'),
  ('Die mittelalterliche Stadt', 'Handwerk und Zünfte: Ausbildung und Regeln'),
  ('Die mittelalterliche Stadt', 'Handel, Kaufleute und soziale Gruppen in der Stadt'),
 ],
 'Deutsch': [('Rechtschreibstrategien','Wörter verlängern und zerlegen'),('Rechtschreibstrategien','Verlängern bei d/t und g/k begründen'),('Nominalisierung','Verben als Nomen erkennen'),('Nominalisierung','Adjektive nach etwas und viel großschreiben'),('Argumentation','Behauptung, Begründung und Beispiel'),('Argumentation','Ein Gegenargument entkräften')],
 'Mathematik': [('Brüche verstehen','Zähler und Nenner an Anteilen erklären'),('Brüche verstehen','Brüche erweitern und kürzen'),('Bruchrechnung','Ungleichnamige Brüche addieren'),('Bruchrechnung','Gemischte Zahlen umwandeln'),('Sachaufgaben','Anteile in einer Alltagssituation berechnen'),('Sachaufgaben','Rechenweg und Ergebnis prüfen')],
}

def curriculum(day):
    from datetime import timedelta
    lessons=[];homework=[]
    for subject,units in DEMO_UNITS.items():
        for i,(group,text) in enumerate(units):
            d=(day-timedelta(days=(len(units)-i)*3)).isoformat()
            lid=-(len(lessons)+1)
            lessons.append(dict(id=lid,date=d,subject_name=subject,text=text,future=False,missed_minutes=45 if i==2 else 0,demo_group=group))
            if i%3==1:homework.append(dict(id=lid,assigned_date=d,due_date=(day-timedelta(days=(len(units)-i)*3-2)).isoformat(),subject_name=subject,text='Erkläre mit einem eigenen Beispiel: '+text))
    return lessons,homework
