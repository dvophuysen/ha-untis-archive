"""Subject overview from existing topic self-reports; no new proficiency score."""
from fastapi import APIRouter, Depends, Query
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..subject_names import SubjectCatalog
router = APIRouter()


def summarize_goals(goals, catalog):
    groups = {}
    histories = {}
    for goal in goals:
        if goal['kind'] != 'lesson':
            continue
        match = catalog.resolve(goal['subject'], goal.get('subject_id'))
        sid = goal.get('subject_id') or goal['subject']
        group = groups.setdefault(sid, dict(
            subject_id=sid, subject_name=match['label'] if match else goal['subject'],
            items=[], topics=[], feedback_count=0, understood_topics=0,
            uncertain_topics=0, partial_topics=0, difficult_topics=0, unrated_topics=0,
        ))
        history = histories.setdefault(sid, {})
        for source in goal['sources']:
            if source.get('rating') in (1, 2, 3) and source.get('date') and source.get('id') is not None:
                history[source['id']] = dict(lesson_id=source['id'], date=source['date'],
                    start_time=source.get('start_time'), rating=source['rating'])
        rating = goal.get('rating')
        counter = {3: 'understood_topics', 2: 'partial_topics', 1: 'difficult_topics'}.get(rating, 'unrated_topics')
        group[counter] += 1
        item = dict(lesson_id=goal['key'], date=goal['date'], rating=rating,
                    lstext=goal['title'], state=goal['state'], url=goal['url'],
                    source_count=goal['source_count'], uncertain_count=goal['uncertain_count'],
                    sources=goal['sources'], session_id=goal.get('session_id'))
        group['topics'].append(item)
        if rating in (1, 2):
            group['uncertain_topics'] += 1
            group['items'].append(item)
    for sid, group in groups.items():
        history = sorted(histories[sid].values(), key=lambda item: (
            item['date'], str(item['start_time'] or '').replace(':', '').zfill(4), item['lesson_id']))
        group['feedback_count'] = len(history)
        # Actual ordered observations, not smoothed or inferred ability values.
        group['feedback_history'] = history[-12:]
    return list(groups.values())


@router.get('/accounts/{account_id}/oral-suggestions')
async def oral_suggestions(account_id: int, horizon_days: int = Query(default=7, ge=1, le=21),
                           user: CurrentUser = Depends(get_current_user)):
    assert_account_access(user, account_id)
    from .plan import plan as shared_plan
    plan = await shared_plan(account_id, user)
    return dict(groups=summarize_goals(plan['goals'], SubjectCatalog(account_id)), errors=plan.get('errors', []))
