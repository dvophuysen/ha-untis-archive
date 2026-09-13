"""Compact subject state from the same consolidated goals used by the coach."""
from fastapi import APIRouter, Depends, Query
from ..auth import CurrentUser,assert_account_access,get_current_user
from ..subject_names import SubjectCatalog
router=APIRouter()

@router.get('/accounts/{account_id}/oral-suggestions')
async def oral_suggestions(account_id:int,horizon_days:int=Query(default=7,ge=1,le=21),user:CurrentUser=Depends(get_current_user)):
    assert_account_access(user,account_id)
    from .plan import plan as shared_plan
    plan=await shared_plan(account_id,user);groups={};catalog=SubjectCatalog(account_id)
    for g in plan['goals']:
        if g['kind']!='lesson':continue
        match=catalog.resolve(g['subject'],g.get('subject_id'))
        sid=g.get('subject_id') or g['subject']
        group=groups.setdefault(sid,dict(subject_id=sid,subject_name=match['label'] if match else g['subject'],items=[],feedback_count=0,understood_topics=0,uncertain_topics=0))
        group['feedback_count']+=sum(x.get('rating') in (1,2,3) for x in g['sources'])
        if g['rating']==3:group['understood_topics']+=1
        if g['rating'] not in (1,2):continue
        group['uncertain_topics']+=1
        group['items'].append(dict(lesson_id=g['key'],date=g['date'],rating=g['rating'],lstext=g['title'],state=g['state'],url=g['url'],source_count=g['source_count'],uncertain_count=g['uncertain_count'],sources=g['sources'],session_id=g.get('session_id')))
    return dict(groups=list(groups.values()),errors=plan.get('errors',[]))
