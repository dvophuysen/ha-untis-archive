import io
import json
from contextlib import closing

from PIL import Image
import pytest
from test_learning import env  # noqa: F401
from backend import db, vocab_mini as mini
from backend.vocab_catalog import CatalogError


def source():
    out = io.BytesIO(); Image.new('RGB', (100, 200), 'white').save(out, 'PNG')
    with closing(db.webapp_conn()) as c, c:
        return c.execute("INSERT INTO materials(account_id,kind,subject_name,title,file_bytes,created_at,updated_at) "
                         "VALUES(1,'book_page','Englisch','Original',?,'now','now')", (out.getvalue(),)).lastrowid


def test_no_fallback_to_foundry_one_or_another_model(monkeypatch):
    monkeypatch.setattr(mini, 'ai_tiers', lambda: {'klein': {'model': 'gpt-5-mini', 'foundry': '1'}, 'hoch': {'model': 'other', 'foundry': '2'}})
    with pytest.raises(CatalogError, match='Kein Rückfall'):
        mini.mini_tier()


@pytest.mark.asyncio
async def test_mini_results_stay_isolated_and_cache_depends_on_image_and_protocol(env, monkeypatch):
    mid = source(); calls = []
    monkeypatch.setattr(mini, 'ai_tiers', lambda: {'klein': {'model': 'gpt-5-mini', 'foundry': '2'}})
    async def complete(*args, **kw):
        calls.append(kw)
        return json.dumps({'printed_page': 10, 'rows': [], 'events': [], 'issues': []}), {'tokens': 3}, 'test'
    monkeypatch.setattr(mini.ai, 'complete', complete)
    spec = mini.PageSpec(material_id=mid, number=10, side='full')
    first = await mini.read_page(1, 'Englisch', spec)
    assert first['review_required'] and first['foundry'] == '2'
    assert calls[0]['tier'] == 'klein' and len(calls[0]['images']) == 2
    assert await mini.read_page(1, 'Englisch', spec) == first
    assert len(calls) == 1
    monkeypatch.setattr(mini, 'PROTOCOL', 'changed')
    await mini.read_page(1, 'Englisch', spec)
    assert len(calls) == 2
    with closing(db.webapp_conn()) as c, c:
        out = io.BytesIO(); Image.new('RGB', (100, 200), 'black').save(out, 'PNG')
        c.execute('UPDATE materials SET file_bytes=? WHERE id=?', (out.getvalue(), mid))
    await mini.read_page(1, 'Englisch', spec)
    assert len(calls) == 3
    with closing(db.webapp_conn()) as c:
        for table in ('vocab_words', 'vocab_attempts', 'vocab_catalog_runs'):
            assert c.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_sequence_is_sorted_and_cannot_skip_a_page(monkeypatch):
    order = []
    async def read(account, subject, spec):
        order.append(spec.number); return {}
    monkeypatch.setattr(mini, 'read_page', read)
    specs = [mini.PageSpec(material_id=n, number=n, side='full') for n in (12, 10, 11)]
    await mini.read_sequence(1, 'Englisch', specs, 10)
    assert order == [10, 11, 12]
    with pytest.raises(CatalogError, match='lückenlos'):
        await mini.read_sequence(1, 'Englisch', specs[:2], 10)
    assert order == [10, 11, 12]


@pytest.mark.asyncio
async def test_wrong_child_cannot_transcribe_an_original(env, monkeypatch):
    mid = source()
    monkeypatch.setattr(mini, 'ai_tiers', lambda: {'klein': {'model': 'gpt-5-mini', 'foundry': '2'}})
    with pytest.raises(CatalogError, match='nicht für dieses Kind'):
        await mini.read_page(2, 'Englisch', mini.PageSpec(material_id=mid, number=10, side='full'))
