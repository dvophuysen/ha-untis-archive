"""Activation must not rewrite learning history, even across fresh sources."""
import hashlib
import json
from contextlib import closing

import pytest
from test_learning import env  # noqa: F401
from backend import db, vocab_catalog as catalog


def fixture(account=1, word='gate'):
    with closing(db.webapp_conn()) as c, c:
        mid = c.execute("INSERT INTO materials(account_id,kind,subject_name,title,file_bytes,created_at,updated_at) "
                        "VALUES(?,'book_page','Englisch','Page',?,'now','now')", (account, b'original page')).lastrowid
    page = {'number': 10, 'material_id': mid, 'source_sha256': hashlib.sha256(b'original page').hexdigest(),
            'rows': [{'foreign_word': word, 'meanings': ['Gate']}], 'begins': 'new',
            'boundaries': [{'at': 0, 'action': 'open', 'title': 'Unit 1', 'level': 0, 'kind': 'unit', 'evidence': 'Unit 1'}]}
    reviewed(page)
    return {'book_key': 'test-edition', 'title': 'Test book', 'start_page': 10, 'end_page': 10, 'pages': [page]}


def reviewed(page):
    page['review'] = {'method': 'source_visual_review', 'reviewer': 'test reference', 'row_count': len(page['rows']),
                      'content_sha256': catalog._digest({k: page[k] for k in ('rows', 'boundaries', 'begins')})}


def legacy(mid, word='gate', practiced=True):
    with closing(db.webapp_conn()) as c, c:
        wid = c.execute("INSERT INTO vocab_words(account_id,subject,material_id,foreign_word,plain,meanings_json,created_at) "
                        "VALUES(1,'ENGLISCH',?,?,?,'[\"Gate\"]','old')", (mid, word, word)).lastrowid
        if practiced:
            c.execute("INSERT INTO vocab_attempts(account_id,word_id,stage,direction,answer,result,created_at) "
                      "VALUES(1,?,1,'from','Gate','correct','2026-09-10T10:00:00')", (wid,))
        return wid


def attempts():
    with closing(db.webapp_conn()) as c:
        return [dict(r) for r in c.execute('SELECT * FROM vocab_attempts ORDER BY id')]


def publish(payload):
    run = catalog.stage(1, 'Englisch', payload)
    return catalog.activate(1, run['id'], run['content_digest'])


def test_speech_hint_uses_active_catalog_membership(env):
    from backend import vocab
    payload = fixture(word='airport')
    legacy(payload['pages'][0]['material_id'], word='obsolete', practiced=False)
    publish(payload)
    unit = vocab.units(1, 'Englisch')[0]['unit']
    hint = vocab.prompt_for(1, 'Englisch', unit, 'into')
    assert 'airport' in hint
    assert 'obsolete' not in hint
    assert 'Gate' in vocab.prompt_for(1, 'Englisch', unit, 'from')


def test_staging_does_not_change_words_history_or_active_catalog(env):
    payload = fixture(); legacy(payload['pages'][0]['material_id']); before = attempts()
    run = catalog.stage(1, 'Englisch', payload)
    assert run['valid']
    assert attempts() == before
    assert not catalog.active(1, 'Englisch')
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT count(*) FROM vocab_words').fetchone()[0] == 1
        assert c.execute('SELECT count(*) FROM vocab_learning_aliases').fetchone()[0] == 0


def test_reimport_new_material_id_preserves_all_old_ids_and_attempts(env):
    old = fixture(); wid = legacy(old['pages'][0]['material_id']); before = attempts()
    new = fixture(); published = publish(new)
    assert attempts() == before
    assert published['preservation']['attempt_digest_before'] == published['preservation']['attempt_digest_after']
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT word_id FROM vocab_catalog_entries').fetchone()[0] == wid
        assert c.execute('SELECT count(*) FROM vocab_words').fetchone()[0] == 1


def test_duplicates_in_different_sections_share_one_word_and_preserve_both_histories(env):
    first = fixture(); second = fixture()
    a = legacy(first['pages'][0]['material_id']); b = legacy(second['pages'][0]['material_id']); before = attempts()
    p = second['pages'][0]; p['rows'] *= 2
    p['boundaries'].append({'at': 1, 'action': 'open', 'title': 'Airport', 'kind': 'box', 'level': 1, 'evidence': 'box title'})
    p['boundaries'].append({'at': 2, 'action': 'close', 'target': 'p10:r1:n1', 'evidence': 'bottom border'})
    reviewed(p)
    result = publish(second)
    assert result['words'] == 1 and result['occurrences'] == 2
    assert attempts() == before
    with closing(db.webapp_conn()) as c:
        assert [r[0] for r in c.execute('SELECT canonical_id FROM vocab_learning_aliases ORDER BY word_id')] == [a, a]
        assert [r[0] for r in c.execute('SELECT id FROM vocab_words ORDER BY id')] == [a, b]


def test_changed_source_or_review_blocks_activation_without_side_effects(env):
    payload = fixture(); wid = legacy(payload['pages'][0]['material_id']); before = attempts()
    run = catalog.stage(1, 'Englisch', payload)
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE materials SET file_bytes=? WHERE id=?", (b'changed', payload['pages'][0]['material_id']))
    with pytest.raises(catalog.CatalogError, match='Freigabe gesperrt'):
        catalog.activate(1, run['id'], run['content_digest'])
    assert attempts() == before and not catalog.active(1, 'Englisch')
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT count(*) FROM vocab_catalog_entries').fetchone()[0] == 0


def test_unmapped_practiced_word_and_wrong_account_block_activation(env):
    payload = fixture(); legacy(payload['pages'][0]['material_id'], 'unmapped')
    before = attempts(); run = catalog.stage(1, 'Englisch', payload)
    with pytest.raises(catalog.CatalogError, match='bereits geübte'):
        catalog.activate(1, run['id'], run['content_digest'])
    with pytest.raises(catalog.CatalogError, match='nicht gefunden'):
        catalog.activate(2, run['id'], run['content_digest'])
    assert attempts() == before


def test_edited_transcription_invalidates_review_and_missing_last_page_blocks(env):
    payload = fixture(); payload['pages'][0]['rows'][0]['meanings'] = ['invented']
    payload['end_page'] = 11
    result = catalog.stage(1, 'Englisch', payload)
    assert not result['valid']
    assert {'content_review_missing_or_stale', 'incomplete_page_range'} <= {i['code'] for i in result['issues']}


def test_repeated_activation_and_replacement_are_idempotent_and_archive_old_catalog(env):
    payload = fixture(); run = catalog.stage(1, 'Englisch', payload)
    catalog.activate(1, run['id'], run['content_digest'])
    assert catalog.activate(1, run['id'], run['content_digest'])['already_active']
    second = publish(fixture())
    assert [r['id'] for r in catalog.active(1, 'Englisch')] == [second['id']]
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT status FROM vocab_catalog_runs WHERE id=?', (run['id'],)).fetchone()[0] == 'archived'
        assert c.execute('SELECT count(*) FROM vocab_words').fetchone()[0] == 1


def test_learning_state_is_shared_and_section_list_keeps_its_own_order(env):
    from backend import vocab
    first = fixture(); second = fixture()
    wid = legacy(first['pages'][0]['material_id']); legacy(second['pages'][0]['material_id'])
    p = second['pages'][0]
    p['rows'] = [{'foreign_word': 'gate', 'meanings': ['Gate']},
                 {'foreign_word': 'delay', 'meanings': ['Verspätung']},
                 {'foreign_word': 'gate', 'meanings': ['Flugsteig']}]
    p['boundaries'].append({'at': 1, 'action': 'open', 'title': 'Airport', 'kind': 'section', 'level': 1, 'evidence': 'Airport'})
    reviewed(p); publish(second)
    unit = vocab.units(1, 'Englisch')[0]
    assert unit['words'] == 2 and unit['s1']['sitzt'] == 1
    cards = vocab.cards(1, 'Englisch', unit['unit'], 1, 'from')
    assert len(cards) == 2
    gate = next(w for w in cards if w['id'] == wid)
    assert gate['state']['s1']['stage'] == 'sitzt'
    assert gate['meanings'] == ['Gate', 'Flugsteig']
    ordered = catalog.cards(1, 'Englisch', unit['unit'], 1, 100, unit['sections'][0]['section'], book_order=True)
    assert [w['foreign_word'] for w in ordered] == ['delay', 'gate']
    before = attempts()
    vocab.attempt(1, vocab.AttemptIn(word_id=wid, stage=1, direction='from', answer='Flugsteig', seconds=3))
    assert attempts()[:len(before)] == before


def test_catalog_routes_require_parent_and_account_and_get_does_not_mutate(env):
    from backend.routers import vocab as routes
    from test_learning import child
    client, state, _ = env
    client.app.include_router(routes.router, prefix='/api')
    payload = fixture()
    prefix = '/api/accounts/1/learning/vocab/Englisch'
    response = client.post(prefix + '/catalogs', json={'payload': payload})
    assert response.status_code == 200
    run = response.json()
    body = {'digest': run['content_digest']}
    assert client.post(prefix.replace('/1/', '/2/') + f'/catalogs/{run["id"]}/activate', json=body).status_code == 404
    assert client.post(prefix + f'/catalogs/{run["id"]}/activate', json=body).status_code == 200
    before = attempts()
    assert client.get(prefix + '/units').json()['reading'] == 0
    assert client.post(prefix + '/extract', json={'material_ids': [payload['pages'][0]['material_id']]}).status_code == 409
    assert attempts() == before
    child(state)
    assert client.post(prefix + '/catalogs', json={'payload': payload}).status_code == 403
    assert client.post(prefix + f'/catalogs/{run["id"]}/activate', json=body).status_code == 403


@pytest.mark.asyncio
async def test_capture_appends_quarantined_original_without_overwriting_existing(env, monkeypatch):
    import io
    from PIL import Image, ImageDraw
    from backend import textbook_context as context
    old = fixture(); mid = old['pages'][0]['material_id']; legacy(mid); before = attempts()
    image = Image.new('RGB', (600, 900), 'white'); draw = ImageDraw.Draw(image)
    for y in range(40, 850, 25):
        draw.text((30, y), 'gate       Flugsteig       A sample vocabulary row', fill='black')
    out = io.BytesIO(); image.save(out, 'PNG')
    monkeypatch.setattr(context, 'book_and_credentials', lambda *a, **kw: ({'title': 'Test book'}, {'configured': True}))
    async def fetch(*a, **kw):
        return {'shots': [(10, out.getvalue())], 'status': 'loaded', 'seen': None}
    monkeypatch.setattr(context, 'fetch_pages', fetch)
    result = await catalog.capture_sources(1, 'Englisch', [10])
    assert result['sources'][0]['material_id'] != mid
    assert not result['sources'][0]['printed_page_verified']
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT file_bytes FROM materials WHERE id=?', (mid,)).fetchone()[0] == b'original page'
        new = c.execute('SELECT hidden,origin,analysis_state FROM materials WHERE id=?', (result['sources'][0]['material_id'],)).fetchone()
        assert tuple(new) == (1, 'vocab_capture', 'ready')
    assert attempts() == before
