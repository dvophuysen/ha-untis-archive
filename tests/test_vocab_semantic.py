import asyncio
import json
import pytest
from fastapi import HTTPException
from test_vocab_catalog import env, fixture, legacy, attempts
from backend import db, vocab, vocab_semantic as sem
from backend.routers import vocab as routes


def seeded():
    p = fixture()
    return legacy(p['pages'][0]['material_id'], practiced=False)


def body(wid, answer='Tor', **kw):
    return vocab.AttemptIn(word_id=wid, stage=1, direction='from', answer=answer, **kw)


def test_exact_does_not_accept_negation_or_edit_distance():
    w = {'foreign_word': 'Geografía', 'meanings_json': '["Erdkunde"]'}
    assert sem.exact(w, body(1, 'Erdkunde.'))
    for answer in ['nicht Erdkunde', 'Erdkunde (nicht)', 'Erdkunde oder Mathematik', 'Erdkunde und falsch', 'Erdkund']:
        assert not sem.exact(w, body(1, answer))
    w['meanings_json'] = '["berühmt sein"]'
    assert not sem.exact(w, body(1, 'beliebt sein'))


def test_reviewed_alternatives_are_bound_to_book_direction_and_language():
    w = {'subject':'Spanisch', 'foreign_word':'Geografía', 'meanings_json':'["Erdkunde"]'}
    assert sem.reviewed(w, body(1, 'Geografie.'))['result'] == 'correct'
    assert sem.reviewed(w, body(1, 'nicht Geografie')) is None
    into = body(1, 'Geografie'); into.direction = 'into'
    assert sem.reviewed(w, into) is None
    assert sem.reviewed({**w, 'meanings_json':'["Biologie"]'}, body(1,'Geografie')) is None
    assert sem.reviewed({**w, 'subject':'Englisch'}, body(1,'Geografie')) is None


@pytest.mark.parametrize('decision,result,count', [('accept','correct',1),('reject','incorrect',1),('clarify','unclear',0)])
def test_semantic_verdict_and_evidence(env, decision, result, count):
    client,state,patch = env; wid = seeded(); before = attempts()
    patch.setattr(sem, 'mini_tier', lambda: 'klein')
    async def complete(account, purpose, prompt, context, **kwargs):
        assert kwargs['tier'] == 'klein'
        assert context['answer'] == 'Tor'
        return json.dumps({'decision':decision,'reason':'Meaning check','input_quality':'clear','specificity':'equivalent' if decision=='accept' else 'different'}), {}, 'test-call'
    patch.setattr(sem.ai, 'complete', complete)
    # Confirm cannot turn a semantic clarification into a success.
    got = asyncio.run(sem.submit(1, body(wid, confirm=True)))
    assert got['result'] == result
    assert len(attempts()) == len(before) + count
    if count:
        with db.webapp_conn() as c:
            evidence = c.execute('SELECT evidence_json FROM vocab_answer_assessments').fetchone()[0]
        assert json.loads(evidence)['call_id'] == 'test-call'
        assert 'Im Buch: gate · Gate' in got['feedback']
    else:
        assert got['can_confirm'] is False


@pytest.mark.parametrize('failure', ['provider', 'json', 'decision', 'tier'])
def test_unavailable_never_marks_wrong(env, failure):
    _,_,patch=env; wid=seeded()
    def tier():
        if failure == 'tier': raise sem.CatalogError('not configured')
        return 'klein'
    async def complete(*a, **kw):
        if failure == 'provider': raise HTTPException(502, 'down')
        return ('not json' if failure == 'json' else '{"decision":"maybe"}'), {}, 'x'
    patch.setattr(sem,'mini_tier',tier);patch.setattr(sem.ai,'complete',complete)
    assert asyncio.run(sem.submit(1,body(wid)))['result'] == 'unclear'
    assert attempts() == []


def test_ownership_checked_before_call_and_exact_needs_no_ai(env):
    _,_,patch=env; wid=seeded()
    async def forbidden(*a,**kw): raise AssertionError('No paid call allowed')
    patch.setattr(sem.ai,'complete',forbidden)
    with pytest.raises(HTTPException) as e: asyncio.run(sem.submit(2,body(wid)))
    assert e.value.status_code == 404
    assert asyncio.run(sem.submit(1,body(wid,'Gate')))['result'] == 'correct'


def test_active_source_change_while_waiting_does_not_grade(env):
    _,_,patch=env; wid=seeded()
    patch.setattr(sem,'mini_tier',lambda:'klein')
    async def changed(*a,**kw):
        with db.webapp_conn() as c:
            c.execute('UPDATE vocab_words SET meanings_json=? WHERE id=?', ('["Tür"]',wid));c.commit()
        return '{"decision":"accept","reason":"synonym","input_quality":"clear","specificity":"equivalent"}',{},'call'
    patch.setattr(sem.ai,'complete',changed)
    with pytest.raises(HTTPException) as e: asyncio.run(sem.submit(1,body(wid)))
    assert e.value.status_code == 409
    assert attempts() == []


def test_real_route_uses_semantic_and_rejects_client_override(env):
    client,state,patch=env;client.app.include_router(routes.router,prefix='/api');wid=seeded()
    patch.setattr(sem,'mini_tier',lambda:'klein')
    async def complete(*a,**kw):return '{"decision":"reject","reason":"other meaning","input_quality":"clear","specificity":"different"}',{},'call'
    patch.setattr(sem.ai,'complete',complete)
    payload=body(wid,confirm=True).model_dump()
    assert client.post('/api/accounts/1/learning/vocab/attempts',json=payload).json()['result']=='incorrect'
    payload['assessment']={'result':'correct'}
    assert client.post('/api/accounts/1/learning/vocab/attempts',json=payload).status_code==422
