"""Persistently authenticated, read-only, account-scoped analysis API.

No arbitrary SQL, credentials, raw provider payloads or file downloads.
"""
from __future__ import annotations

import hmac
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from ..config import SETTINGS

router = APIRouter(prefix='/integration/learning', tags=['learning-read-access'])

# source, FROM clause, account expression, public columns, date basis, modified basis
DATASETS = {}

def dataset(name, source, columns, date_field=None, modified=None, joins='', account='d.account_id'):
    DATASETS[name] = (source, f'{name} d {joins}', account, columns.split(), date_field, modified)

dataset('accounts','archive','id name',account='d.id')
dataset('lessons','archive','id account_id untis_period_id date start_time end_time subject_untis_id subject_name teacher_untis_id teacher_name code lstext lstext_manual_override subst_text info was_absent absence_reason is_supervision_guess supervision_manual_override student_group last_updated_at','date','last_updated_at')
dataset('homework','archive','id account_id untis_homework_id untis_lesson_id subject_untis_id subject_name text assigned_date due_date completed first_seen_at last_updated_at','assigned_date','last_updated_at')
dataset('absences','archive','id account_id start_date end_date start_time end_time reason text is_excused excuse_status last_updated_at','start_date','last_updated_at')
dataset('master_schoolyear','archive','id account_id name startDate endDate last_updated_at','startDate','last_updated_at')
dataset('master_holidays','archive','id account_id name longName startDate endDate last_updated_at','startDate','last_updated_at')
dataset('lesson_checkins','app','id account_id lesson_id rating note created_at updated_at untis_period_id','created_at','updated_at')
dataset('caught_up','app','id account_id lesson_id caught_up_at note','caught_up_at','caught_up_at')
dataset('tasks','app','id account_id title subject_untis_id subject_name task_type status estimated_minutes due_date due_time lesson_id notes source created_at updated_at completed_at','due_date','updated_at')
dataset('task_subitems','app','id task_id title done position',joins='JOIN tasks t ON t.id=d.task_id',account='t.account_id')
dataset('task_time_log','app','id task_id started_at ended_at minutes','started_at',joins='JOIN tasks t ON t.id=d.task_id',account='t.account_id')
dataset('hidden_courses','app','account_id course_key subject_untis_id subject_name teacher_untis_id teacher_name created_at','created_at')
dataset('account_settings','app','account_id default_daily_budget_minutes budget_overrides_json auto_budget school_section_override updated_at',modified='updated_at')
dataset('account_exam_calendars','app','account_id ha_entity_id exclude_keywords updated_at',modified='updated_at')
dataset('subject_aliases','app','id account_id alias subject_name subject_untis_id created_at','created_at')
dataset('manual_exams','app','id account_id exam_date subject_name subject_untis_id title note created_at','exam_date')
dataset('exam_overrides','app','id account_id source_key decision subject_name subject_untis_id updated_at',modified='updated_at')
dataset('exam_progress','app','account_id exam_key learn_state learn_note grade grade_points updated_at',modified='updated_at')
dataset('learning_profiles','app','id account_id school_year grade region school_type personal_goal daily_minutes max_sessions study_days ai_enabled active created_at','created_at')
PROFILE_JOIN='JOIN learning_profiles p ON p.id=d.profile_id'
TOPIC_JOIN='JOIN learning_topics t ON t.id=d.topic_id JOIN learning_profiles p ON p.id=t.profile_id'
ACTIVITY_JOIN='JOIN learning_activities a ON a.id=d.activity_id JOIN learning_topics t ON t.id=a.topic_id JOIN learning_profiles p ON p.id=t.profile_id'
dataset('learning_topics','app','id profile_id subject title objective method status priority source_note target_date created_at updated_at','created_at','updated_at',PROFILE_JOIN,'p.account_id')
dataset('learning_activities','app','id topic_id kind afb operator prompt explanation hint solution criteria minutes published origin source_ids created_at','created_at',joins=TOPIC_JOIN,account='p.account_id')
dataset('learning_sessions','app','id activity_id snapshot answer help_used outcome difficulty minutes started_at completed_at','started_at',joins=ACTIVITY_JOIN,account='p.account_id')
dataset('learning_reviews','app','activity_id next_due streak last_outcome last_session_id','next_due',joins=ACTIVITY_JOIN,account='p.account_id')


# Die gelesenen Inhaltsverzeichnisse: Grundlage der Kapitelregel und der
# Wortschatzteile, deshalb auch von außen nachlesbar.
dataset('book_chapters','app','id account_id book_title number title kind level start_page end_page belongs_to locked created_at','created_at')

dataset('learning_day_preferences','app','account_id day load updated_at','day','updated_at')
dataset('learning_plan_links','app','account_id goal_key skill_id')
dataset('learning_plan_blocks','app','account_id day session_id goal_key minutes','day')
dataset('learning_skill_state','app','skill_id account_id level label due_date last_day rationale rule_version','last_day')

# Mentor history and evidence remain account-scoped. Binary files are excluded.
for name,cols,dt in [
 ('mentor_sessions','id account_id subject goal is_test is_demo phase status version max_minutes elapsed_seconds turns help_count summary context_hash created_at updated_at','updated_at'),
 ('mentor_messages','id account_id session_id role text payload created_at','created_at'),
 ('mentor_skills','id account_id subject title objective source_json created_at updated_at','updated_at'),
 ('mentor_evidence','id account_id skill_id session_id exam_attempt_id task_json answer result rationale help_used source variant_hash invalidated created_at','created_at'),
 ('mentor_reviews','skill_id account_id due_date last_evidence_id updated_at','updated_at'),
 ('mentor_ai_calls','id account_id session_id purpose month day model status reserved_micro charged_micro input_tokens output_tokens input_rate output_rate created_at finished_at error','created_at'),
 ('mentor_jobs','account_id status next_run updated_at error','updated_at'),
 ('mentor_exams','id account_id title subject scope_json tasks_json minutes status is_demo created_at published_at','created_at'),
 ('mentor_exam_attempts','id account_id exam_id is_test status answers_json snapshot feedback_json elapsed_seconds started_at submitted_at','started_at')]:
    dataset(name,'app',cols,dt)


def authenticate(x_learning_read_key: str | None = Header(default=None)) -> set[int]:
    key=os.environ.get('LEARNING_READ_TOKEN','')
    try:
        allowed={int(x.strip()) for x in os.environ.get('LEARNING_READ_ACCOUNTS','').split(',') if x.strip()}
    except ValueError:
        allowed=set()
    if len(key)<32 or not allowed or any(x<1 for x in allowed):
        raise HTTPException(503,'Lesezugang ist nicht konfiguriert')
    if not x_learning_read_key or not hmac.compare_digest(x_learning_read_key.encode(),key.encode()):
        raise HTTPException(401,'Lesezugang benötigt einen gültigen Schlüssel')
    return allowed


def open_readonly(source):
    path=SETTINGS.history_db_path if source=='archive' else SETTINGS.webapp_db_path
    conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    conn.row_factory=sqlite3.Row
    if source == 'archive':
        from ..attendance import install_attendance_view
        install_attendance_view(conn)
    conn.execute('PRAGMA query_only=ON')
    return conn


@router.get('')
def manifest(allowed:set[int]=Depends(authenticate)):
    return {'api_version':1,'read_only':True,'account_ids':sorted(allowed),
            'datasets':{k:{'date_basis':v[4],'modified_basis':v[5]} for k,v in DATASETS.items()},
            'pagination':'after uses the last _cursor; repeat until has_more=false. Pages are not a cross-request snapshot.',
            'refresh':'updated_since supports listed modified_basis fields. Use full rescan to detect deletions.',
            'notes':'Archive rows retain cancelled/hidden courses and partial absences. Lesson attendance ignores explicit lateness; absences retains the source records. Apply hidden_courses and time overlap before counting missed lessons. Self-reports are not objective mastery.'}


@router.get('/{name}')
def read_dataset(name:str, account_id:int=Query(ge=1), after:int=Query(default=0,ge=0),
                 limit:int=Query(default=100,ge=1,le=250), start:date|None=None, end:date|None=None,
                 updated_since:datetime|None=None, allowed:set[int]=Depends(authenticate)):
    if account_id not in allowed: raise HTTPException(403,'Kind ist für diesen Lesezugang nicht freigegeben')
    if name not in DATASETS: raise HTTPException(404,'Unbekannter Datensatz')
    source,from_sql,account,columns,date_field,modified=DATASETS[name]
    if start and end and start>end: raise HTTPException(422,'Beginn muss vor dem Ende liegen')
    if (start or end) and not date_field: raise HTTPException(422,'Dieser Datensatz hat keinen Datumsfilter')
    if updated_since and not modified: raise HTTPException(422,'Dieser Datensatz unterstützt keinen Änderungsfilter')
    try:
        with closing(open_readonly(source)) as c:
            c.execute('BEGIN')
            present={r['name'] for r in c.execute(f'PRAGMA table_info("{name}")')}
            if not present:
                return {'dataset':name,'available':False,'rows':[],'has_more':False,'next_after':None,'reason':'Tabelle in dieser Version nicht vorhanden'}
            selected=[col for col in columns if col in present]
            missing=[col for col in columns if col not in present]
            if (start or end) and date_field not in present or updated_since and modified not in present:
                raise HTTPException(503,'Benötigte Filterspalte fehlt in dieser Datenbankversion')
            where=[f'{account}=?','d.rowid>?']; args=[account_id,after]
            if start:
                where.append(f'substr(d."{date_field}",1,10)>=?');args.append(start.isoformat())
            if end:
                where.append(f'substr(d."{date_field}",1,10)<=?');args.append(end.isoformat())
            if updated_since:
                where.append(f'julianday(d."{modified}")>=julianday(?)');args.append(updated_since.isoformat())
            fields=', '.join(f'd."{col}"' for col in selected)
            rows=[dict(r) for r in c.execute(f'SELECT d.rowid AS _cursor,{fields} FROM {from_sql} WHERE '+ ' AND '.join(where)+' ORDER BY d.rowid LIMIT ?',[*args,limit+1])]
            more=len(rows)>limit;rows=rows[:limit]
    except (sqlite3.Error,OSError):
        raise HTTPException(503,'Datenquelle derzeit nicht lesbar; kein leeres Ergebnis behauptet') from None
    return {'dataset':name,'account_id':account_id,'available':True,'missing_columns':missing,
            'read_at':datetime.now(timezone.utc).isoformat(),'rows':rows,'has_more':more,
            'next_after':rows[-1]['_cursor'] if more else None}
