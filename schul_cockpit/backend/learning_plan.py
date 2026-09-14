"""One deterministic plan for homework, mentor, retention and subject preparation.

No model calls. Source IDs never imply mastery; skills carry replayable evidence.
The seven-day view is a projection, not fabricated future learning outcomes.
"""
from contextlib import closing
from datetime import date, timedelta
import json
from .db import webapp_conn
from .learning import today_local, now_iso
from . import mentor_context as mc

INTERVALS = (2, 7, 14, 30, 60)


def replay(evidence):
    level = 0; due = None; last_day = None; success_day = None; first_success = None; failure_day = None; variants = set()
    label = 'Noch nicht selbstständig geprüft'; rationale = ''
    for e in evidence:
        if e.get('invalidated'): continue
        day = e['created_at'][:10]
        try: d = date.fromisoformat(day)
        except ValueError: continue
        last_day = day; rationale = e['rationale']
        if e['result'] == 'uncertain':
            label = 'Bewertung ungeklärt · keine Rückstufung'
            continue
        if e['result'] == 'correct' and not e['help_used']:
            # Same-day answers and a known task never grow retention intervals.
            if day != success_day and e['variant_hash'] not in variants:
                level = min(5, level + 1); success_day = day
                if first_success is None:first_success=d
                variants.add(e['variant_hash'])
            label = 'Mit Abstand selbstständig gezeigt' if level >= 2 and first_success and (d-first_success).days>=7 else 'Selbstständig gezeigt · später prüfen'
            due = (d + timedelta(days=INTERVALS[max(0, level-1)])).isoformat()
        else:
            if e['result'] in ('incorrect','partial') and failure_day!=day:
                level=max(0,level-1);failure_day=day
            label = 'Mit Hilfe gelungen · Kurzcheck offen' if e['result']=='correct' else 'Teilproblem noch offen'
            due = (d + timedelta(days=2)).isoformat()
    return dict(level=level, due_date=due, last_day=last_day, label=label, rationale=rationale)


def refresh_skill(c, account, skill):
    ev = [dict(r) for r in c.execute('SELECT e.* FROM mentor_evidence e LEFT JOIN mentor_sessions s ON s.id=e.session_id LEFT JOIN mentor_exam_attempts a ON a.id=e.exam_attempt_id WHERE e.account_id=? AND e.skill_id=? AND e.invalidated=0 AND COALESCE(s.is_test,0)=0 AND COALESCE(a.is_test,0)=0 ORDER BY e.created_at,e.id',(account,skill))]
    state = replay(ev)
    c.execute('INSERT INTO learning_skill_state(skill_id,account_id,level,label,due_date,last_day,rationale) VALUES(?,?,?,?,?,?,?) ON CONFLICT(skill_id) DO UPDATE SET level=excluded.level,label=excluded.label,due_date=excluded.due_date,last_day=excluded.last_day,rationale=excluded.rationale', (skill,account,state['level'],state['label'],state['due_date'],state['last_day'],state['rationale']))
    if ev and state['due_date']:
        c.execute('INSERT INTO mentor_reviews VALUES(?,?,?,?,?) ON CONFLICT(skill_id) DO UPDATE SET due_date=excluded.due_date,last_evidence_id=excluded.last_evidence_id,updated_at=excluded.updated_at',(skill,account,state['due_date'],ev[-1]['id'],now_iso()))
    else: c.execute('DELETE FROM mentor_reviews WHERE skill_id=? AND account_id=?',(skill,account))
    return state


def goal_key(lesson):
    # Reuse verified discovery clusters even when the original lesson wording differs.
    if lesson.get('topic',{}).get('id'):
        return 'discovered:'+str(lesson['topic']['id'])
    # Same topic across dates stays one goal; all hourly feedback remains in sources.
    return 'topic:'+mc.fingerprint([lesson.get('subject_untis_id') or lesson['subject_name'].strip().casefold(),' '.join(lesson['text'].split()).casefold()])[:24]


def legacy_goal_key(lesson):
    return 'lesson:'+mc.fingerprint([lesson.get('subject_untis_id') or lesson['subject_name'],lesson['date'],' '.join(lesson['text'].split())])[:24]


def link_session(c, account, session, skill):
    if not skill or session['is_test']: return
    source=json.loads(session['source_json'] or '{}')
    key=source.get('goal_key')
    if key:c.execute('INSERT OR IGNORE INTO learning_plan_links VALUES(?,?,?)',(account,key,skill))


def catalogue(account, snapshot=None):
    s=snapshot or mc.snapshot(account); day=today_local(); groups={}; lesson_keys={}; aliases={}
    next_lesson={}
    for r in sorted(s['lessons'],key=lambda x:(x['date'],str(x.get('start_time') or '').replace(':','').zfill(4),x['id']),reverse=True):
        subject=(r.get('subject_name') or '').strip()
        if not subject:continue
        if r.get('future'):
            next_lesson[subject]=min(next_lesson.get(subject,'9999'),r['date']);continue
        if not r['text'].strip() or r.get('rating')==4:continue
        # Was die Auswertung als organisatorisch oder unklar eingestuft hat, ist
        # kein Lernziel. Ohne diese Zeile wurde der rohe Eintragstext zum Titel,
        # und „AG-Vorstellung in der Aula" stand als Übungsaufgabe im Plan.
        if r.get('no_topic'):continue
        if not mc.practice_subject(subject):continue
        key=goal_key(r);lesson_keys[r['id']]=key;aliases[legacy_goal_key(r)]=key
        g=groups.setdefault(key,dict(key=key,kind='lesson',subject=subject,subject_id=r.get('subject_untis_id'),topic_id=r.get('topic',{}).get('id'),title=r.get('topic',{}).get('title') or r['text'][:150],lesson_id=r['id'],sources=[],rating=r.get('rating'),catch_up_open=False,date=r['date'],skill_ids=[],sessions=[],state='Noch nicht geprüft',due_date=None,last_day=None,reason='',minutes=8))
        g['sources'].append({k:r.get(k) for k in ('id','untis_period_id','date','start_time','text','rating','note','catch_up_open')})
        if g['rating'] is None and r.get('rating') in (1,2,3):g['rating']=r['rating']
        g['catch_up_open'] |= r.get('catch_up_open',False)
    with closing(webapp_conn()) as c:
        skills=[dict(r) for r in c.execute('SELECT * FROM mentor_skills WHERE account_id=?',(account,))]
        sessions=[dict(r) for r in c.execute("SELECT * FROM mentor_sessions WHERE account_id=? AND is_test=0 AND COALESCE(json_extract(source_json,'$.mode'),'')!='homework_help' ORDER BY id",(account,))]
        for session in sessions:
            source=json.loads(session['source_json'] or '{}');key=source.get('goal_key')
            if key in aliases:
                key=aliases[key];source['goal_key']=key
                c.execute('UPDATE mentor_sessions SET source_json=? WHERE id=? AND account_id=?',(json.dumps(source,ensure_ascii=False),session['id'],account))
            if not key and source.get('lesson_id') in lesson_keys:
                key=lesson_keys[source['lesson_id']]
                # Do not silently attach an obsolete source version to changed text.
                if source.get('text') and not any(x['text']==source['text'] for x in groups[key]['sources']):key=None
            if key in groups:
                groups[key]['sessions'].append({k:session[k] for k in ('id','status','summary','updated_at')})
                if session['skill_id']:c.execute('INSERT OR IGNORE INTO learning_plan_links VALUES(?,?,?)',(account,key,session['skill_id']))
        links={}
        for r in c.execute('SELECT * FROM learning_plan_links WHERE account_id=?',(account,)):
            target=aliases.get(r['goal_key'],r['goal_key'])
            if target not in links.setdefault(r['skill_id'],[]):links[r['skill_id']].append(target)
        for skill in skills:
            state=refresh_skill(c,account,skill['id'])
            # Old deletions and withdrawn assessments must not create empty reviews.
            if state['last_day'] is None:continue
            keys=[k for k in links.get(skill['id'],[]) if k in groups]
            if not keys:
                key='skill:'+str(skill['id']);keys=[key]
                groups[key]=dict(key=key,kind='review',subject=skill['subject'],subject_id=None,title=skill['title'],sources=[],skill_ids=[],sessions=[],rating=None,catch_up_open=False,date=skill['created_at'][:10],state='',minutes=5)
            for key in keys:
                g=groups[key];g['skill_ids'].append(skill['id']);g.setdefault('skill_states',[]).append(dict(id=skill['id'],title=skill['title'],**state))
        # Existing learning cards are kept as self-reports, never promoted to AI evidence.
        legacy=[dict(r) for r in c.execute("SELECT a.id,a.minutes,a.prompt,t.subject,t.title,r.next_due,ls.completed_at,ls.outcome FROM learning_activities a JOIN learning_topics t ON t.id=a.topic_id JOIN learning_profiles p ON p.id=t.profile_id LEFT JOIN learning_reviews r ON r.activity_id=a.id LEFT JOIN learning_sessions ls ON ls.id=r.last_session_id WHERE p.account_id=? AND p.active=1 AND a.published=1 AND t.status='active'",(account,))]
        for a in legacy:
            key='activity:'+str(a['id'])
            groups[key]=dict(key=key,kind='activity',activity_id=a['id'],subject=a['subject'],title=a['title'],sources=[],skill_ids=[],sessions=[],rating=None,catch_up_open=False,date=day.isoformat(),state='Selbst eingeschätzt · kein unabhängiger Nachweis' if a['outcome'] else 'Eigene Übung',due_date=a['next_due'] or day.isoformat(),last_day=(a['completed_at'] or '')[:10],minutes=a['minutes'])
    for g in groups.values():
        g['source_count']=len(g['sources'])
        g['uncertain_count']=sum(x.get('rating') in (1,2) for x in g['sources'])
        g['previous_keys']=[k for k,v in aliases.items() if v==g['key']]
        states=g.get('skill_states',[])
        if states:
            dates=[x['due_date'] for x in states if x['due_date']]
            g['due_date']=min(dates) if dates else None
            g['last_day']=max((x['last_day'] or '' for x in states),default='')
            g['state']=' · '.join(dict.fromkeys(x['label'] for x in states))
            g['open_question']='; '.join(x['rationale'] for x in states if x['rationale'])[:800]
            if len(states)==1:g['skill_id']=states[0]['id']
        if g['sessions']:
            recent=g['sessions'][-1]
            g['session_id']=recent['id'];g['active']=recent['status']=='active'
            g['worked_day']=recent['updated_at'][:10]
            if not states:g['state']='Bearbeitet · selbstständiger Kurzcheck offen'
            if not g.get('due_date'):g['due_date']=(date.fromisoformat(g['worked_day'])+timedelta(days=2)).isoformat()
        related=[t for t in s['tasks'] if t.get('lesson_id') in {x['id'] for x in g['sources']} and t.get('status')=='done' and t.get('completed_at')]
        if related:
            finished=max(t['completed_at'][:10] for t in related)
            g['homework_done_day']=finished
            if not states and not g['sessions']:
                g['state']='Zugehörige Hausaufgabe erledigt · Können noch nicht geprüft'
                g['due_date']=(date.fromisoformat(finished)+timedelta(days=2)).isoformat()
        g['next_lesson']=next_lesson.get(g['subject'])
        if not g.get('due_date'):g['due_date']=(date.fromisoformat(g['date'])+timedelta(days=2)).isoformat()
        g['reason']='Fälliger Kurzcheck nach dem Üben' if states or g['sessions'] else 'Zuletzt selbst als unsicher gemeldet' if g['rating'] in (1,2) else 'Versäumten Stoff einordnen; Können noch unbekannt' if g['catch_up_open'] else 'Stichprobe: auch verstandenen Stoff später abrufen'
        g['source_note']='Unterricht vom '+g['date'] if g['sources'] else 'Gespeicherte Übung / Lernbeobachtung'
        if g.get('next_lesson'):g['reason']+=' · nächste Stunde '+g['next_lesson']
        g['url']='#/learning?goal='+g['key']
    return list(groups.values()),s


def usage(c,account,day):
    d=day.isoformat()
    blocks=c.execute('SELECT COALESCE(SUM(minutes),0),COUNT(*) FROM learning_plan_blocks WHERE account_id=? AND day=?',(account,d)).fetchone()
    # Earlier sessions retain their allotted block; early completion never refills the day.
    old=c.execute("SELECT COALESCE(SUM(max_minutes),0),COUNT(*) FROM mentor_sessions WHERE account_id=? AND is_test=0 AND COALESCE(json_extract(source_json,'$.mode'),'')!='homework_help' AND substr(created_at,1,10)=? AND id NOT IN (SELECT session_id FROM learning_plan_blocks WHERE account_id=? AND day=?)",(account,d,account,d)).fetchone()
    legacy=c.execute("SELECT COALESCE(SUM(MAX(COALESCE(s.minutes,0),COALESCE(json_extract(s.snapshot,'$.minutes'),a.minutes))),0),COUNT(*) FROM learning_sessions s JOIN users u ON u.id=s.user_id JOIN learning_activities a ON a.id=s.activity_id JOIN learning_topics t ON t.id=a.topic_id JOIN learning_profiles p ON p.id=t.profile_id WHERE p.account_id=? AND u.role='child' AND u.is_admin=0 AND (substr(s.completed_at,1,10)=? OR (s.completed_at IS NULL AND substr(s.started_at,1,10)=?))",(account,d,d)).fetchone()
    homework=c.execute("SELECT COALESCE(SUM(COALESCE(estimated_minutes,20)),0) FROM tasks WHERE account_id=? AND status='done' AND substr(completed_at,1,10)=?",(account,d)).fetchone()[0]
    exams=c.execute("SELECT COALESCE(SUM(MAX(elapsed_seconds,COALESCE(json_extract(snapshot,'$.minutes'),0)*60)),0) FROM mentor_exam_attempts WHERE account_id=? AND is_test=0 AND substr(started_at,1,10)=?",(account,d)).fetchone()[0]
    return dict(learning=blocks[0]+old[0]+legacy[0]+(exams+59)//60,slots=blocks[1]+old[1]+legacy[1],homework=homework)


def envelope(account,day,profile,budget_override=None):
    from .routers.afternoon import _budget_for_today
    try: total,source=_budget_for_today(account,day)
    except Exception:total,source=0,{'source':'unavailable'}
    allowed=bool(profile and profile['daily_minutes']>0 and day.weekday() in json.loads(profile['study_days']))
    if total==0 and allowed and day.weekday()>=5 and source.get('source')=='erlass':total=profile['daily_minutes']
    if budget_override is not None:total=budget_override;source={'source':'ad_hoc_override'}
    return max(0,total),source,allowed


def build(account,exams=(),snapshot=None,budget_override=None):
    goals,s=catalogue(account,snapshot);day=today_local();profile=s['profile'];week=[];scheduled=set();scheduled_topics=set();subject_counts={};deferred=[]
    with closing(webapp_conn()) as c:
        tasks=[dict(r) for r in c.execute("SELECT * FROM tasks WHERE account_id=? AND status IN ('open','in_progress') ORDER BY COALESCE(due_date,'9999'),id",(account,))]
        used=usage(c,account,day)
        day_loads={r['day']:r['load'] for r in c.execute('SELECT day,load FROM learning_day_preferences WHERE account_id=?',(account,))}
    pending_tasks=tasks[:]
    for offset in range(7):
        d=day+timedelta(days=offset);ds=d.isoformat();total,source,allowed=envelope(account,d,profile,budget_override if offset==0 else None)
        already=used if offset==0 else dict(learning=0,homework=0,slots=0)
        must=[t for t in pending_tasks if t.get('due_date') and t['due_date']<=(d+timedelta(days=1)).isoformat()]
        homework=sum(t.get('estimated_minutes') if t.get('estimated_minutes') is not None else 20 for t in must)
        load=day_loads.get(ds,'normal')
        if load=='busy':total=min(total,homework+already['homework']+already['learning']+5)
        elif load=='room':total=max(total,homework+already['homework']+already['learning']+(profile or {}).get('daily_minutes',15)+15)
        remaining=max(0,total-homework-already['homework']-already['learning']) if allowed or load=='room' else 0
        slots=max(0,(profile or {}).get('max_sessions',0)+(1 if load=='room' else 0)-already['slots'])
        imminent={e.get('subject_name') for e in exams if ds<e.get('date','')<=(d+timedelta(days=3)).isoformat()}
        def topic_key(g):
            return (g['subject'],g['topic_id']) if g.get('topic_id') is not None and not g.get('skill_states') else None
        # Group only planning occasions, never independent evidence or mastery.
        candidates=[]
        for original in goals:
            g=dict(original)
            g['next_lesson']=min((r['date'] for r in s['lessons'] if r.get('future') and r.get('subject_name')==g['subject'] and r['date']>=ds),default=None)
            g['reason']=g['reason'].split(' · nächste Stunde ')[0]
            if g['next_lesson']:g['reason']+=' · nächste Stunde '+g['next_lesson']
            candidates.append(g)
        available=[g for g in candidates if g['key'] not in scheduled and topic_key(g) not in scheduled_topics and (g['due_date']<=ds or g['subject'] in imminent) and not (offset==0 and (g.get('last_day')==ds or g.get('worked_day')==ds))]
        exam_dates={e.get('subject_name'):e.get('date') for e in sorted(exams,key=lambda e:e.get('date',''),reverse=True) if e.get('date','')>ds}
        def rank(g):
            exam=exam_dates.get(g['subject']);urgent=bool(exam and exam<=(d+timedelta(days=10)).isoformat())
            return (not urgent,subject_counts.get(g['subject'],0),g['rating'] not in (1,2),not bool(g.get('skill_states')),not g['catch_up_open'],g.get('next_lesson') or '9999',g['due_date'],g['key'])
        # Workload determines the proposal; free capacity is never a target.
        need=sum(g['rating'] in (1,2) or g['catch_up_open'] or bool(g.get('skill_states')) for g in available)
        urgent=any(g['subject'] in imminent for g in available)
        target=5 if not need else min(30,8*min(need,3)+5)
        if urgent:target=max(target,20)
        if load=='busy':target=5
        elif load=='room':target+=10 if need else 5
        remaining=min(remaining,max(0,target-already['learning']))
        if not need:slots=min(slots,1 if load!='room' else 2)
        available.sort(key=rank)
        # One check of previously positive/unmeasured material per active day,
        # within the same budget, rotates subjects across the weekly projection.
        stable=[g for g in available if g['rating'] not in (1,2) and not g['catch_up_open'] and not g.get('sessions') and not g.get('skill_states')]
        if stable and (slots>1 or d.toordinal()%3==0):
            place=1 if slots>1 else 0
            available.insert(min(place,len(available)),available.pop(available.index(stable[0])))
        actions=[];subjects=set()
        for g in available:
            if len(actions)>=slots:break
            if g['subject'] in subjects:continue
            minutes=g['minutes'] if g['kind']=='activity' else min(g['minutes'],remaining)
            if minutes<3 or minutes>remaining:continue
            actions.append({**g,'minutes':minutes,'planned_date':ds,'reason':g['reason']+(' · Klausur '+exam_dates[g['subject']] if g['subject'] in exam_dates else '')})
            subjects.add(g['subject']);scheduled.add(g['key']);remaining-=minutes
            subject_counts[g['subject']]=subject_counts.get(g['subject'],0)+1
            if topic_key(g) is not None:scheduled_topics.add(topic_key(g))
        for t in must:pending_tasks.remove(t)
        planned=sum(g['minutes'] for g in actions)
        week.append(dict(date=ds,budget_minutes=total,budget_source=source,study_day=allowed or load=='room',day_load=load,target_minutes=target,load_reason='Wenig Bedarf: kurzer Erhaltungscheck genügt' if not need else 'Klausur steht kurz bevor: gezielte Vorbereitung' if urgent else 'Offene Anliegen und fällige Wiederholungen gezielt aufgreifen',homework=must,homework_minutes=homework,used_minutes=already['learning']+already['homework'],learning_used_minutes=already['learning'],used_slots=already['slots'],actions=actions,planned_minutes=planned+homework,remaining_minutes=remaining,overload_minutes=max(0,homework-max(0,total-already['learning']-already['homework'])),message='Das ist der Vorschlag für heute. Du kannst den Tag leichter planen oder bei Bedarf mehr aufgreifen.'))
    today=week[0]
    for g in goals:
        if g['key'] not in {x['key'] for x in today['actions']} and g['due_date']<=day.isoformat():deferred.append({**g,'defer_reason':'Heute bereits bearbeitet; später erneut prüfen' if g.get('worked_day')==day.isoformat() or g.get('last_day')==day.isoformat() else 'Nicht zusätzlich eingeplant: Zeitrahmen, Lerntage und Fachwechsel beachten'})
    return dict(account_id=account,date=day.isoformat(),today=today,week=week,goals=goals,deferred=deferred,errors=s['errors'],read_at=s['read_at'],upcoming_exams=list(exams),rule_version='1',workload='viel' if today['overload_minutes'] else 'überschaubar' if today['planned_minutes'] else 'frei',must=today['homework'],should=[],cram=[])


def reserve_resume(c, account, session, day):
    """Account for continuing a real mentor session on another local day."""
    if json.loads(session.get('source_json') or '{}').get('mode')=='homework_help':return
    if session['is_test'] or session['created_at'][:10]==day.isoformat():return
    if c.execute('SELECT 1 FROM learning_plan_blocks WHERE account_id=? AND day=? AND session_id=?',(account,day.isoformat(),session['id'])).fetchone():return
    from fastapi import HTTPException
    p=c.execute('SELECT * FROM learning_profiles WHERE account_id=? AND active=1',(account,)).fetchone()
    if not p:raise HTTPException(409,'Bitte zuerst den Lernrahmen für dieses Schuljahr prüfen.')
    total,_,allowed=envelope(account,day,dict(p));used=usage(c,account,day)
    must=c.execute("SELECT COALESCE(SUM(COALESCE(estimated_minutes,20)),0) FROM tasks WHERE account_id=? AND status IN ('open','in_progress') AND due_date<=?",(account,(day+timedelta(days=1)).isoformat())).fetchone()[0]
    available=min(p['daily_minutes']-used['learning'],total-must-used['homework']-used['learning'])
    rest=max(1,session['max_minutes']-(session['elapsed_seconds']//60))
    voluntary=json.loads(session.get('source_json') or '{}').get('voluntary') is True
    if not voluntary and (not allowed or used['slots']>=p['max_sessions'] or available<rest):
        raise HTTPException(409,'Diese Fortsetzung passt heute nicht mehr in den Zeitrahmen. Du kannst jederzeit abschließen; im Plan steht der nächste Lerntag.')
    key=json.loads(session['source_json'] or '{}').get('goal_key','session:'+str(session['id']))
    c.execute('INSERT INTO learning_plan_blocks VALUES(?,?,?,?,?)',(account,day.isoformat(),session['id'],key,rest))
