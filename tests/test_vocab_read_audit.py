from contextlib import closing
from backend import db
from test_learning import env

def test_source_audit_is_account_scoped_and_read_only(env):
    from backend.routers import read_access as r
    client, state, patch = env
    client.app.include_router(r.router, prefix='/api')
    patch.setattr(r, 'SETTINGS', db.SETTINGS)
    patch.setenv('LEARNING_READ_TOKEN', 'a' * 48)
    patch.setenv('LEARNING_READ_ACCOUNTS', '1')
    headers = {'X-Learning-Read-Key': 'a' * 48}
    base = '/api/integration/learning'
    with closing(db.webapp_conn()) as c:
        for mid, account in [(900, 1), (901, 2)]:
            c.execute("INSERT INTO materials(id,account_id,filename,mime_type,file_bytes,created_at,updated_at) VALUES(?,?,?,'image/png',?,'now','now')",
                      (mid, account, 'private.png', b'original-' + str(account).encode()))
    assert client.get(base + '/materials/900/file?account_id=1').status_code == 401
    assert client.get(base + '/materials/901/file?account_id=2', headers=headers).status_code == 403
    assert client.get(base + '/materials/901/file?account_id=1', headers=headers).status_code == 404
    response = client.get(base + '/materials/900/file?account_id=1', headers=headers)
    assert response.content == b'original-1'
    assert response.headers['cache-control'] == 'private, no-store'
    listing = client.get(base + '/materials?account_id=1', headers=headers).json()
    assert [x['id'] for x in listing['rows']] == [900]
    assert 'file_bytes' not in listing['rows'][0]
    assert client.post(base + '/materials/900/file?account_id=1', headers=headers).status_code == 405
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT COUNT(*) FROM vocab_attempts').fetchone()[0] == 0
        assert c.execute('SELECT analysis_state FROM materials WHERE id=900').fetchone()[0] == 'pending'




def test_recent_activity_is_readable_before_an_update(env):
    """Vor einem Update: War in den letzten Minuten jemand in der App, Kind oder Eltern?"""
    from backend.routers import read_access as r
    from backend import usage_report
    client, state, patch = env
    client.app.include_router(r.router, prefix='/api')
    patch.setattr(r, 'SETTINGS', db.SETTINGS)
    patch.setenv('LEARNING_READ_TOKEN', 'a' * 48)
    patch.setenv('LEARNING_READ_ACCOUNTS', '1')
    usage_report.record_ping(1, 'child', 'today', 60, True)
    usage_report.record_ping(2, 'child', 'today', 60, True)
    rows = client.get('/api/integration/learning/usage_days?account_id=1',
                      headers={'X-Learning-Read-Key': 'a' * 48}).json()['rows']
    assert [(x['account_id'], x['actor'], x['opens']) for x in rows] == [(1, 'child', 1)]
    assert rows[0]['last_at'] and 'views_json' not in rows[0]
