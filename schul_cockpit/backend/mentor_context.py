"""Deterministic, provenance-bearing context and rotation; no model calls."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from .db import history_conn, webapp_conn
from .courses import hidden_keys, lesson_is_hidden
from .learning import today_local, now_iso
from .request_cache import memo


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def same_subject(left,right):
    return bool(left and right and str(left).strip().casefold()==str(right).strip().casefold())


def rows(c, table, columns, account_id, suffix='', args=()):
    have={r[1] for r in c.execute(f'PRAGMA table_info("{table}")')}
    if 'account_id' not in have: return []
    cols=[x for x in columns.split() if x in have]
    return [dict(r) for r in c.execute(f'SELECT {",".join(cols)} FROM {table} WHERE account_id=? '+suffix,(account_id,*args))]


def school_start(c, account_id, day):
    fallback=date(day.year-(day.month<8),8,1).isoformat()
    years=rows(c,'master_schoolyear','startDate endDate',account_id)
    def iso(v):
        t=str(v or '').replace('-','')[:8]
        return f'{t[:4]}-{t[4:6]}-{t[6:8]}' if len(t)==8 and t.isdigit() else ''
    starts=[iso(y.get('startDate')) for y in years if iso(y.get('startDate'))<=day.isoformat()<=iso(y.get('endDate'))]
    return max(starts) if starts else fallback


def missed_minutes(lesson, absences):
    def stamp(day,t,end=False):
        t=str(t or ('23:59' if end else '00:00'))
        if t.isdigit(): t=t.zfill(4);t=t[:2]+':'+t[2:]
        return datetime.fromisoformat(str(day)+'T'+t)
    try:
        a=stamp(lesson['date'],lesson.get('start_time'));b=stamp(lesson['date'],lesson.get('end_time'),True)
        spans=[]
        for x in absences:
            left=max(a,stamp(x['start_date'],x.get('start_time')));right=min(b,stamp(x['end_date'],x.get('end_time'),True))
            if right>left: spans.append((left,right))
        spans.sort();merged=[]
        for left,right in spans:
            if merged and left<=merged[-1][1]: merged[-1]=(merged[-1][0],max(right,merged[-1][1]))
            else: merged.append((left,right))
        return int(sum((b-a).total_seconds()/60 for a,b in merged))
    except (KeyError,ValueError,TypeError): return None


def snapshot(account_id, include_previous=False, include_all_homework=False):
    day=today_local(); errors=[]
    with closing(webapp_conn()) as c:
        p=c.execute('SELECT * FROM learning_profiles WHERE account_id=? AND active=1',(account_id,)).fetchone()
        ratings={r['lesson_id']:dict(r) for r in c.execute('SELECT lesson_id,rating,note,updated_at FROM lesson_checkins WHERE account_id=?',(account_id,))}
        caught={r[0] for r in c.execute('SELECT lesson_id FROM caught_up WHERE account_id=?',(account_id,))}
        tasks=rows(c,'tasks','id title subject_name task_type status estimated_minutes due_date lesson_id notes updated_at completed_at',account_id,'ORDER BY updated_at DESC LIMIT 160')
        reviews=[dict(r) for r in c.execute('SELECT s.*,r.due_date FROM mentor_skills s JOIN mentor_reviews r ON r.skill_id=s.id WHERE s.account_id=? ORDER BY r.due_date LIMIT 60',(account_id,))]
        recent=[dict(r) for r in c.execute('SELECT id,subject,goal,status,summary,updated_at FROM mentor_sessions WHERE account_id=? AND is_test=0 ORDER BY id DESC LIMIT 20',(account_id,))]
        settings=c.execute('SELECT * FROM mentor_settings WHERE account_id=?',(account_id,)).fetchone()
        discovered={r['lesson_id']:dict(r) for r in c.execute('SELECT i.lesson_id,i.fingerprint,t.id,t.subject,t.title,t.objective,d.explanation,d.bridge,d.prerequisites,d.outlook FROM learning_discovery_items i JOIN learning_topics t ON t.id=i.topic_id JOIN learning_discovery_topics d ON d.topic_id=t.id WHERE i.account_id=? AND i.profile_id=?',(account_id,p['id'] if p else -1))}
        # Die Auswertung stuft Einträge ohne Lerninhalt ausdrücklich als unklar
        # ein und stellt eine Rückfrage. Dieses Urteil wurde bisher gespeichert
        # und danach übergangen: Organisatorisches landete als Übungsziel im Plan.
        unclear={r['lesson_id']:dict(r) for r in c.execute('SELECT lesson_id,fingerprint,note,unclear_kind FROM learning_discovery_items WHERE account_id=? AND profile_id=? AND topic_id IS NULL',(account_id,p['id'] if p else -1))}
    try:
        with closing(history_conn()) as c:
            start=school_start(c,account_id,day)
            if include_previous: start=str(int(start[:4])-1)+start[4:]
            lessons=rows(c,'lessons','id untis_period_id date start_time end_time subject_name subject_untis_id teacher_untis_id teacher_name lstext lstext_manual_override was_absent is_supervision_guess supervision_manual_override code last_updated_at',account_id,
                         'AND date>=? AND date<=? ORDER BY date DESC,id DESC LIMIT 6001',(start,(day+timedelta(days=7)).isoformat()))
            absence=rows(c,'absences','start_date end_date start_time end_time reason',account_id)
            absence=[a for a in absence if str(a.get('reason') or '').strip().casefold() not in {'verspätet','verspätung'}]
            homework=rows(c,'homework','id untis_lesson_id subject_name text assigned_date due_date completed',account_id,'AND assigned_date>=? ORDER BY assigned_date DESC LIMIT '+('8001' if include_all_homework else '200'),(start,))
            if include_all_homework and len(homework)>8000:errors.append('Die Hausaufgabenhistorie überschreitet die vollständige Lesemenge.')
        hidden=hidden_keys(account_id)
        clipped=len(lessons)>6000
        clean=[]
        for r in lessons[:6000]:
            if lesson_is_hidden(r,hidden) or str(r.get('code') or '').casefold()=='cancelled': continue
            override=r.get('supervision_manual_override')
            if override if override is not None else r.get('is_supervision_guess'): continue
            text=r.get('lstext_manual_override') or r.get('lstext') or ''
            n=missed_minutes(r,absence) if r.get('was_absent') else 0
            r.update(text=text[:1800],text_truncated=len(text)>1800,rating=ratings.get(r['id'],{}).get('rating'),note=(ratings.get(r['id'],{}).get('note') or '')[:500],
                     missed_minutes=n,caught_up=r['id'] in caught,catch_up_open=bool(r.get('was_absent') and r['id'] not in caught and (n is None or n>=15)),future=r['date']>day.isoformat())
            r.pop('teacher_name',None);r.pop('lstext_manual_override',None);r.pop('lstext',None)
            stamp=fingerprint([r['date'],r.get('subject_name'),r['text']])
            topic=discovered.get(r['id'])
            # Reuse only a cluster whose underlying lesson still matches.
            if topic and topic['subject']==r.get('subject_name') and topic['fingerprint']==stamp:
                r['topic']={k:topic[k] for k in ('id','title','objective','explanation','bridge','prerequisites','outlook')}
            else:
                open_question=unclear.get(r['id'])
                if open_question and open_question['fingerprint']==stamp:
                    # Ohne Lerninhalt ist es kein Lernziel. Ist nur die
                    # Beschreibung zu knapp, bleibt die Stunde eine Stunde;
                    # sie trägt dann eine offene Frage statt zu verschwinden.
                    r['no_topic']=open_question['unclear_kind']=='organisatorisch'
                    r['open_question']=open_question['note'] or ''
            clean.append(r)
        lessons=clean
    except (sqlite3.Error,OSError):
        start=None;lessons=[];homework=[];clipped=False;errors.append('Unterrichtsarchiv konnte nicht gelesen werden.')
    from .subject_names import SubjectCatalog
    try:
        catalog=SubjectCatalog(account_id)
        tasks=[catalog.task(t) for t in tasks]
    except (sqlite3.Error,OSError):
        errors.append('Fachzuordnung derzeit nicht verfügbar.')
    profile=dict(p) if p else None
    return dict(profile=profile,enabled=bool(not settings or settings['enabled']),background=bool(settings and settings['background_enabled']),
                since=start,lessons=lessons,homework=homework,tasks=tasks,reviews=reviews,recent=recent,errors=errors,truncated=clipped,read_at=now_iso())


@memo(shallow=True)
def _snapshot_once(account_id):
    return snapshot(account_id)


def shared_snapshot(account_id):
    """snapshot() einmal je Aufruf (request_cache.scope): Der Mentor-Überblick
    las ihn zweimal, selbst und über den Plan. Stunden und Aufgaben teilen sich
    die Leser, die sie nicht verändern; die oberste Ebene und die Fehlerliste
    (an die der Plan Warnungen hängt) bekommt jeder neu. Ohne scope() wie snapshot()."""
    s=_snapshot_once(account_id)
    return {**s,'errors':list(s['errors'])}


# Fächer, in denen eine Übungsaufgabe am Handy nichts zu suchen hat: Bewegung
# lässt sich so nicht nachholen, und die Verfügungsstunde ist kein Lernfach.
NO_PRACTICE=('sport','schwimm','pause','klassenrat','verfügungs','verfuegungs','klassenlehrer','klassenstunde')


def practice_subject(name):
    return bool((name or '').strip()) and not any(x in (name or '').casefold() for x in NO_PRACTICE)


def candidates(s):
    day=today_local(); seen=set();out=[]
    # Skills due for retention come first; cap any one subject so recent doubts
    # do not permanently displace a subject that was positively self-rated.
    for r in s['reviews']:
        if r['due_date']<=day.isoformat():
            out.append(dict(kind='review',skill_id=r['id'],subject=r['subject'],title=r['title'],reason='Mit Abstand an einer neuen Aufgabe ausprobieren',source={'skill_id':r['id']},rank=0))
    last={}
    for r in s['recent']: last.setdefault(r['subject'],r['updated_at'][:10])
    # Archive-wide events may have lesson text but no subject. They cannot
    # anchor a subject-specific learning session; retain them in the archive.
    pool=[r for r in s['lessons'] if not r['future'] and r['text'].strip()
          and practice_subject(r.get('subject_name')) and not r.get('no_topic')]
    pool.sort(key=lambda r:(r['rating'] not in (1,2),not r['catch_up_open'],last.get(r['subject_name'],''),r['date']),reverse=False)
    for r in pool:
        subject=r.get('subject_name') or 'Unterricht'
        if subject in seen: continue
        seen.add(subject)
        # Pick latest relevant entry within subject, not the first old duplicate.
        options=[x for x in pool if x.get('subject_name')==subject]
        x=max(options,key=lambda x:(x['rating'] in (1,2),x['catch_up_open'],x['date']))
        reason='Verständnis kurz prüfen' if x['rating'] in (1,2) else 'Versäumtes gemeinsam einordnen' if x['catch_up_open'] else 'Kurz schauen, was noch sitzt'
        out.append(dict(kind='lesson',lesson_id=x['id'],subject=subject,title=x.get('topic',{}).get('title') or x['text'][:150],reason=reason,
                        source={'lesson_id':x['id'],'date':x['date'],'text':x['text']},rank=1 if x['rating'] in (1,2) else 2))
    # Rotate the first subject using number of starts today, then offer max 4.
    out.sort(key=lambda r:(last.get(r['subject'],''),r['rank']))
    return out[:12]


def stable_version(subject,goal,source,lessons):
    """Woran sich zeigt, dass eine Antwort des Mentors fachlich überholt ist (A8).

    Der Zug liest den Kontext vor dem Modellaufruf und danach noch einmal; weicht
    dieser Stand ab, wird die Antwort verworfen (409), damit keine Aufgabe und
    keine Einschätzung zu einem geänderten Auftrag gespeichert wird. Gezählt wird
    nur, was die Antwort entwerten kann: Fach, Ziel, Auftrag (Hausaufgabe mit
    Wortlaut, Stunde, Thema) und die Stundentexte. Nicht dazu gehören
    Zeitstempel, Erledigt-Haken, die Auswertung eines gerade hochgeladenen
    Fotos, Material, andere Verläufe und Belege: Die ändern sich im Hintergrund,
    ohne dass die Antwort falsch wird, und kosteten bisher einen bezahlten Zug."""
    src={k:v for k,v in (source or {}).items() if k not in ('loesung','situation','missed','missed_minutes')}
    task=src.get('task')
    if isinstance(task,dict):src['task']={k:task.get(k) for k in ('id','title','notes')}
    return fingerprint(dict(subject=subject,goal=goal,source=src,
                            lessons=[[r.get('id'),r.get('date'),r.get('text')] for r in lessons if (r.get('text') or '').strip()]))


def context(account_id,session,version_only=False):
    """Kontext eines Mentor-Zugs, dazu sein stabiler Stand (stable_version) und
    der Schnappschuss. version_only liest nur, was der Stand braucht: für den
    zweiten Blick nach dem Modellaufruf."""
    s=snapshot(account_id);subject=session['subject']
    lessons=[r for r in s['lessons'] if same_subject(r.get('subject_name'),subject)][:18]
    source=json.loads(session.get('source_json') or '{}')
    # Die selbst gewählten Seiten sind Buchführung der App; beim Mentor kommen
    # sie mit ihrem gelesenen Text an, nicht als Liste von Nummern.
    chosen_pages=source.pop('eingebunden',None) or []
    if source.get('mode') in ('homework_help','homework_check'):
        with closing(webapp_conn()) as c:
            task=c.execute('SELECT id,title,notes,subject_name,status,due_date FROM tasks WHERE id=? AND account_id=?',(source.get('task_id'),account_id)).fetchone()
        source={**source,'task':dict(task)} if task else {**source,'unavailable':True}
        # Die bestätigte Bearbeitung ist die Lösung: gedruckte Seite und
        # Eintragungen des Kindes getrennt, damit die Antworten des Kindes nicht
        # als Buchinhalt gelten (D98, D123).
        chosen=source.get('solution') or {}
        if chosen.get('confirmed') and not version_only:
            from .materials import detail, pupil_only
            page=detail(account_id,chosen['material_id']) or {}
            if page:
                source['loesung']={'wo':' '.join(x for x in (chosen.get('label'),f"S. {chosen['page']}" if chosen.get('page') else '') if x) or page.get('title'),
                                   'abgelegt_am':chosen.get('date'),'titel':page.get('title'),
                                   'gedruckte_seite':(page.get('printed_text') or '')[:6000],
                                   'eintragungen_des_kindes':pupil_only(page.get('content_text') or '')[:120],
                                   'volltext':(page.get('content_text') or '')[:8000],
                                   'hinweis':'Diese Bearbeitung liegt als Bild bei. Sie ist die Lösung des Kindes; frage nicht nach einem Foto.'}
    lesson_materials=[]
    if source.get('lesson_id'):
        focus=next((r for r in s['lessons'] if (r.get('untis_period_id')==source['untis_period_id'] if source.get('untis_period_id') else r['id']==source['lesson_id'])),None)
        situation=source.get('situation')
        source={'lesson_id':focus['id'],'date':focus['date'],'text':focus['text'],'missed':bool(focus.get('catch_up_open')),'missed_minutes':focus.get('missed_minutes')} if focus else {'unavailable':True}
        if situation:source['situation']=situation
        if focus and not version_only:
            # Nachholen arbeitet am Stoff der versäumten Stunde: die Stellen, die
            # der Untis-Text nennt, liegen als Material vor und gehören nach vorn.
            with closing(webapp_conn()) as c:
                lesson_materials=[r[0] for r in c.execute("SELECT DISTINCT material_id FROM source_links WHERE account_id=? AND entry_kind='lesson' AND entry_id=? AND material_id IS NOT NULL",(account_id,focus['id']))]
    version=stable_version(subject,session['goal'],source,lessons)
    if version_only:return None,version,s
    with closing(webapp_conn()) as c:
        msgs=[dict(r) for r in c.execute('SELECT role,text,payload FROM mentor_messages WHERE session_id=? ORDER BY id DESC LIMIT 8',(session['id'],))][::-1]
        for m in msgs: m.pop('payload',None)
        evidence=[dict(r) for r in c.execute('SELECT task_json,answer,result,rationale,help_used,created_at FROM mentor_evidence WHERE account_id=? AND skill_id=? AND invalidated=0 ORDER BY id DESC LIMIT 5',(account_id,session.get('skill_id')))]
    from .materials import for_context
    topic_ids=[lesson['topic']['id'] for lesson in lessons if lesson.get('topic',{}).get('id')]
    materials=for_context(account_id,subject=subject,task_id=(source.get('task') or {}).get('id'),
                          topic_ids=topic_ids,material_ids=lesson_materials,budget=5000,top=3)
    state=dict(grade=(s['profile'] or {}).get('grade'),school_year=(s['profile'] or {}).get('school_year'),subject=subject,goal=session['goal'],
               source=source,lessons=[{k:r.get(k) for k in ['id','date','text','rating','note','missed_minutes','catch_up_open','caught_up']} for r in lessons],
               rating_meaning={'1':'nicht verstanden','2':'teilweise verstanden','3':'verstanden','4':'nur Aufsicht / kein neuer Stoff'},
               tasks=[r for r in s['tasks'] if same_subject(r.get('subject_name'),subject)][:10],
               homework=[r for r in s['homework'] if same_subject(r.get('subject_name'),subject)][:6],
               previous=[r for r in s['recent'] if same_subject(r['subject'],subject) and r['id']!=session['id']][:3],
               evidence=evidence,materials=materials,errors=s['errors'])
    topics={}
    for lesson in lessons:
        t=lesson.get('topic')
        if t and t['id'] not in topics and len(topics)<3:
            topics[t['id']]={k:(v[:700] if isinstance(v,str) else v) for k,v in t.items()}
            topics[t['id']].update(source_lesson_id=lesson['id'],source_date=lesson['date'],status='KI-Themenvorschlag aus dokumentiertem Unterricht; keine gemessene Kompetenz')
    state['topic_connections']=list(topics.values())
    state['book_context']=book_context(account_id,subject,source)
    consolidated={}
    for lesson in lessons:
        normalized=('discovered:'+str(lesson['topic']['id'])) if lesson.get('topic',{}).get('id') else ' '.join((lesson.get('text') or '').split()).casefold()
        if not normalized:continue
        item=consolidated.setdefault(normalized,{'topic':lesson.get('topic',{}).get('title') or lesson['text'],'feedback':[]})
        item['feedback'].append({k:lesson.get(k) for k in ('id','date','rating','note')})
    state['consolidated_topics']=list(consolidated.values())
    if chosen_pages:state['eingebunden']=chosen_materials(account_id,chosen_pages)
    state.update(messages=msgs,summary=session['summary'],phase=session['phase'],current_task=json.loads(session['current_task']) if session['current_task'] else None,
                 help_count=session['help_count'],task_help=bool(session['task_help']),read_at=s['read_at'])
    return state,version,s


# Der ganze Aufruf (Anweisung und Kontext) darf 48 000 Byte haben, sonst bricht
# ai_gateway mit 413 ab. Gekürzt wurde bisher nur der Unterricht; lange
# Kontrollen, eine gelöste Seite mit Volltext oder viele eingebundene Seiten
# liefen darüber (A9). Ziel mit Luft für den Bildaufbau-Hinweis des Gateways.
CONTEXT_BUDGET=44000


def _size(ctx,fixed):
    return fixed+len(json.dumps(ctx,ensure_ascii=False).encode())


def fit_context(ctx,instruction,budget=CONTEXT_BUDGET):
    """Kürzt den Kontext nach Vorrang, bis Anweisung und Kontext ins Budget
    passen. Ein Kontext, der schon passt, bleibt Byte für Byte gleich: Das
    Prompt-Caching (D149) und die Antworten hängen daran. Reihenfolge: ältere
    Nachrichten, der Volltext neben der gedruckten Seite (derselbe Inhalt),
    der Bestand einer Abfrage, eingebundene Seiten, Material, ältere Stunden,
    zuletzt die ältesten Nachrichten selbst. Gibt die gekürzten Teile zurück."""
    fixed=len(instruction.encode())
    if _size(ctx,fixed)<=budget:return []
    done=[]

    def over():return _size(ctx,fixed)>budget

    msgs=ctx.get('messages') or []
    for limit in (1200,400):
        for m in msgs[:-2]:
            if len(m.get('text') or '')>limit:m['text']=m['text'][:limit]+' …'
        done.append(f'nachrichten:{limit}')
        if not over():return done
    loesung=(ctx.get('source') or {}).get('loesung')
    if isinstance(loesung,dict) and loesung.get('gedruckte_seite') and loesung.get('volltext'):
        loesung.pop('volltext');done.append('volltext')
        if not over():return done
    quiz=ctx.get('abfrage')
    if isinstance(quiz,dict) and len(quiz.get('bestand') or [])>30:
        items=quiz['bestand'];keep=[x for x in items if x.get('state') in ('falsch','offen')]
        rest=[x for x in items if x not in keep][-max(0,30-len(keep)):] if len(keep)<30 else []
        quiz['bestand']=[x for x in items if x in keep or x in rest];quiz['gekuerzt']=True;done.append('abfrage')
        if not over():return done
    for limit in (1500,700):
        for page in ctx.get('eingebunden') or []:
            if len(page.get('text') or '')>limit:page['text']=page['text'][:limit];page['gekuerzt']=True
        done.append(f'eingebunden:{limit}')
        if not over():return done
    sheet=ctx.get('arbeitsblatt')
    if isinstance(sheet,dict) and len(sheet.get('text') or '')>2000:
        sheet['text']=sheet['text'][:2000];sheet['gekuerzt']=True;done.append('arbeitsblatt')
        if not over():return done
    for item in ctx.get('materials') or []:
        if len(item.get('inhalt') or '')>800:item['inhalt']=item['inhalt'][:800]
    done.append('material')
    if not over():return done
    for key in ('consolidated_topics','lessons'):
        while over() and len(ctx.get(key) or [])>3:ctx[key].pop()
        done.append(key)
    if not over():return done
    while over() and len(msgs)>2:msgs.pop(0)
    done.append('verlauf')
    return done


# Mehrere eingebundene Seiten sollen den Kontext nicht sprengen: Der ganze
# Aufruf darf 48 000 Byte haben, und der Unterricht will auch noch hinein.
CHOSEN_PAGE_CHARS=3000
CHOSEN_TOTAL_CHARS=12000


def chosen_materials(account_id,entries):
    """Die Seiten, die das Kind im Chat aus seinen Materialien gewählt hat,
    mit ihrem gelesenen Text. [Kind: …] markiert im Text, was das Kind selbst
    eingetragen hat; eintragungen_des_kindes zieht das der Reihe nach heraus.
    Ob eine Seite zusätzlich als Bild beiliegt, trägt erst der Zug ein."""
    from .materials import detail, pupil_only
    out=[];used=0
    for entry in entries:
        page=detail(account_id,entry.get('id'))
        if not page or page.get('hidden'):continue
        full=page.get('content_text') or ''
        room=max(0,min(CHOSEN_PAGE_CHARS,CHOSEN_TOTAL_CHARS-used))
        wo=' '.join(x for x in ((page.get('source_label') or '').strip(),f"S. {page['source_page']}" if page.get('source_page') else '') if x)
        item={'id':page['id'],'titel':page.get('title') or '','wo':wo,
              'datum':page.get('document_date') or (page.get('created_at') or '')[:10],
              'text':full[:room],'eintragungen_des_kindes':pupil_only(full)[:120]}
        if len(full)>room:item['gekuerzt']=True
        # Ein frisches Foto ist noch nicht gelesen: Dann zählt nur das Bild.
        if page.get('analysis_state')!='ready' and not full:item['noch_nicht_gelesen']=True
        used+=len(item['text'])
        out.append(item)
    return out


def book_context(account_id,subject,source):
    """Der Gesamtkontext aus dem Buch: In welchem Kapitel steht die Stelle, die
    gerade dran ist, wie weit reicht es, was gehört dazu."""
    text=' '.join(str(v) for v in ((source.get('task') or {}).get('title'),(source.get('task') or {}).get('notes'),source.get('text')) if v)
    if not text.strip():return None
    try:
        from .textbook_context import book_and_credentials, page_numbers
        from .book_structure import chapters_of, chapter_of, companions
        pages=page_numbers(text,subject)
        if not pages:return None
        book,_=book_and_credentials(account_id,subject=subject)
        if not book:return None
        chapters=chapters_of(account_id,book['title'])
        hit=next((chapter_of(chapters,p) for p in pages if chapter_of(chapters,p)),None)
        if not hit:return None
        return dict(buch=book['title'],kapitel=f"{hit['number']} {hit['title']}".strip(),seiten=[hit['start_page'],hit['end_page']],
                    genannte_seiten=pages,dazu=[dict(titel=c['title'],art=c['kind'],seiten=[c['start_page'],c['end_page']]) for c in companions(chapters,hit)],
                    hinweis='Das Kapitel ist der Zusammenhang, in dem die Aufgabe steht; Erklärungen daran ausrichten, nicht darüber hinaus.')
    except Exception:
        return None