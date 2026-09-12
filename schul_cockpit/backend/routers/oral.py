"""Subject preparation is a view of the shared learning goals."""
from fastapi import APIRouter, Depends, Query
from ..auth import CurrentUser,assert_account_access,get_current_user
from .. import learning_plan as lp
from datetime import date
router=APIRouter()
@router.get('/accounts/{account_id}/oral-suggestions')
async def oral_suggestions(account_id:int,horizon_days:int=Query(default=7,ge=1,le=21),user:CurrentUser=Depends(get_current_user)):
    assert_account_access(user,account_id)
    from .plan import plan as shared_plan
    plan=await shared_plan(account_id,user);groups={}
    for g in plan['goals']:
        if not g.get('next_lesson') or g['rating'] not in (1,2):continue
        delta=(date.fromisoformat(g['next_lesson'])-lp.today_local()).days
        if delta>horizon_days:continue
        sid=g.get('subject_id') or g['subject']
        group=groups.setdefault(sid,dict(subject_id=sid,subject_name=g['subject'],subject_short='',next_date=g['next_lesson'],next_start_hhmm='',days_until_next=delta,items=[]))
        group['items'].append(dict(lesson_id=g['key'],date=g['date'],rating=g['rating'],lstext=g['title'],note='',state=g['state'],due_date=g['due_date'],url=g['url'],session_id=g.get('session_id')))
    return dict(horizon_days=horizon_days,groups=sorted(groups.values(),key=lambda g:g['next_date']))
