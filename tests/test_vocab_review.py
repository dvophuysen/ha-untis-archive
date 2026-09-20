import pytest
from fastapi import HTTPException
from test_vocab_catalog import env, fixture, legacy, attempts
from backend import db, vocab, vocab_review


def test_exclusion_is_reversible_and_preserves_raw_attempt(env):
    p = fixture(); wid = legacy(p['pages'][0]['material_id'])
    with db.webapp_conn() as c:
        c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,result,answer,created_at) VALUES(1,?,1,'from','incorrect','','2026-09-12')", (wid,))
        c.commit()
    original = attempts(); aid = original[-1]['id']
    preview = vocab_review.review(1, 'Englisch', [aid], 'Bedienfehler', True, 1)
    assert attempts() == original
    vocab_review.review(1, 'Englisch', [aid], 'Bedienfehler', True, 1, preview['digest'])
    assert attempts() == original
    with db.webapp_conn() as c:
        state = vocab.word_states(c, 1, [wid])[wid]['s1']
    assert state['wrong_count'] == 0 and state['correct_count'] == 1
    with pytest.raises(HTTPException) as e:
        vocab_review.review(1, 'Englisch', [aid], 'Bedienfehler', True, 1, preview['digest'])
    assert e.value.status_code == 409
    preview = vocab_review.review(1, 'Englisch', [aid], 'Wiederaufnahme', False, 1)
    vocab_review.review(1, 'Englisch', [aid], 'Wiederaufnahme', False, 1, preview['digest'])
    with db.webapp_conn() as c:
        assert vocab.word_states(c, 1, [wid])[wid]['s1']['wrong_count'] == 1
    assert attempts() == original
    with pytest.raises(HTTPException):
        vocab_review.review(2, 'Englisch', [aid], 'Bedienfehler', True, 1)
    with pytest.raises(HTTPException):
        vocab_review.review(1, 'Latein', [aid], 'Bedienfehler', True, 1)
