"""Zwei Foundry-Ressourcen und vier Modellstufen an einer Stelle (D88)."""
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path, ai_env  # noqa: F401
from test_mentor import setup, start, reply, B  # noqa: F401
from backend import ai_gateway as ai, learning as L

FIRST = 'https://alt.example/openai/v1/responses'
SECOND = 'https://neu.example/openai/v1/responses'


def both(patch, **tiers):
    ai_env(patch, url=FIRST, key='schluessel-alt', second={'url': SECOND, 'key': 'schluessel-neu'}, tiers=tiers)
    patch.setitem(ai.RATES, 'test-terra', (5.0, 18.0))
    patch.setitem(ai.RATES, 'test-luna', (0.4, 1.8))


def test_a_tier_names_a_model_a_deployment_and_a_foundry(setup):
    _, _, patch = setup
    both(patch, mittel={'modellname': 'test-terra', 'bereitstellungsname': 'terra-eu', 'foundry': '2'})
    hoch, mittel = L.ai_settings('hoch'), L.ai_settings('mittel')
    assert (hoch['model'], hoch['deployment'], hoch['url']) == ('test', 'test', FIRST)
    assert (mittel['model'], mittel['deployment'], mittel['url']) == ('test-terra', 'terra-eu', SECOND)
    assert (hoch['key'], mittel['key']) == ('schluessel-alt', 'schluessel-neu')
    # Ohne eigenen Bereitstellungsnamen ist er der Modellname.
    assert L.ai_settings('niedrig')['deployment'] == 'test-luna'


def test_a_tier_never_falls_back_to_the_other_foundry(setup):
    _, _, patch = setup
    ai_env(patch, url=FIRST, key='schluessel-alt', tiers={'mittel': {'modellname': 'test-terra', 'foundry': '2'}})
    with pytest.raises(L.AiEndpointMissing):
        L.ai_settings('mittel')
    with pytest.raises(ai.HTTPException) as exc:
        ai.settings_for('mittel')
    assert exc.value.status_code == 503 and 'Foundry 2' in exc.value.detail
    # Die übrigen Stufen bleiben benutzbar.
    assert L.ai_settings('hoch')['url'] == FIRST


def test_the_turn_calls_the_deployment_on_its_own_resource(setup):
    client, _, patch = setup
    both(patch)
    session = start(client)
    calls = []

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, **kwargs):
            calls.append({'url': url, 'key': kwargs['headers']['api-key'], 'model': kwargs['json']['model']})
            body = {'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 10},
                    'output': [{'type': 'message', 'role': 'assistant',
                                'content': [{'type': 'output_text', 'text': json.dumps(reply())}]}]}
            return httpx.Response(200, json=body, request=httpx.Request('POST', url))
    patch.setattr(ai.httpx, 'AsyncClient', FakeClient)

    r = client.post(B + f"/sessions/{session['id']}/turn",
                    json={'text': 'Ich fange an.', 'request_key': 'zug-eins-1', 'version': session['version'], 'kind': 'message'})
    assert r.status_code == 200, r.text
    assert calls[0] == {'url': FIRST, 'key': 'schluessel-alt', 'model': 'test'}

    # Zieht die Stufe „hoch" um und heißt dort anders, folgt derselbe Zug.
    calls.clear()
    both(patch, hoch={'modellname': 'test', 'bereitstellungsname': 'sol-eu', 'foundry': '2'})
    session = client.get(B + f"/sessions/{session['id']}").json()
    r = client.post(B + f"/sessions/{session['id']}/turn",
                    json={'text': 'Weiter.', 'request_key': 'zug-zwei-2', 'version': session['version'], 'kind': 'message'})
    assert r.status_code == 200, r.text
    assert calls[0] == {'url': SECOND, 'key': 'schluessel-neu', 'model': 'sol-eu'}
    # Gebucht wird auf den Modellnamen, nicht auf die Bereitstellung.
    from contextlib import closing
    from backend import db
    with closing(db.webapp_conn()) as c:
        assert {r[0] for r in c.execute('SELECT model FROM mentor_ai_calls')} == {'test'}


def test_the_two_foundries_may_use_different_api_shapes(setup):
    _, _, patch = setup
    ai_env(patch, url='https://alt.example/openai/deployments/test/chat/completions?api-version=2024-10-21',
           key='alt', second={'url': SECOND, 'key': 'neu'},
           tiers={'niedrig': {'modellname': 'test-luna', 'foundry': '2'}})
    assert not L.uses_responses(L.ai_settings('hoch')['url'])
    assert L.uses_responses(L.ai_settings('niedrig')['url'])


def test_a_rate_from_the_configuration_beats_the_table_and_missing_rates_block(setup):
    _, _, patch = setup
    both(patch, hoch={'modellname': 'test', 'foundry': '1', 'preis_eingang': 3.5, 'preis_ausgang': 9.5})
    assert ai.rate_for(L.ai_settings('hoch')) == (3.5, 9.5)
    # Halber Satz zählt nicht: sonst würde stillschweigend zu billig gebucht.
    both(patch, hoch={'modellname': 'test', 'foundry': '1', 'preis_eingang': 3.5})
    assert ai.rate_for(L.ai_settings('hoch')) == ai.RATES['test']
    # Unbekanntes Modell ohne eigenen Satz: kein Aufruf.
    both(patch, hoch={'modellname': 'gpt-neu', 'foundry': '1'})
    assert ai.rate_for(L.ai_settings('hoch')) is None
    with pytest.raises(ai.HTTPException) as exc:
        ai.reserve(1, 'mentor', None, 1000, 100)
    assert exc.value.status_code == 503


def test_the_parent_choice_survives_a_model_swap(setup):
    client, _, patch = setup
    both(patch)
    assert client.put(B + '/budget-limits', json={'opening_model': 'mittel'}).status_code == 200
    assert ai.tier_for(ai.OPENING) == 'mittel'
    # Anderes Modell auf derselben Stufe: die Auswahl bleibt, das Modell wechselt mit.
    both(patch, mittel={'modellname': 'test-luna', 'foundry': '2'})
    assert ai.tier_for(ai.OPENING) == 'mittel'
    assert ai.model_name(ai.tier_for(ai.OPENING)) == 'test-luna'


def test_status_and_log_name_tier_model_and_host(setup):
    _, _, patch = setup
    both(patch, mittel={'modellname': 'test-terra', 'bereitstellungsname': 'terra-eu', 'foundry': '2'})
    status = ai.status()
    assert status['model'] == 'test' and status['models'] == ['hoch', 'mittel', 'niedrig']
    assert status['rates']['mittel'] == {'model': 'test-terra', 'input_per_m': 5.0, 'output_per_m': 18.0, 'foundry': '2'}
    overview = ai.endpoint_overview()
    assert 'hoch: test über Foundry 1 (alt.example)' in overview
    assert 'mittel: test-terra als terra-eu über Foundry 2 (neu.example)' in overview
    # Ohne Kostensatz sagt es die Zeile, statt still zu rechnen.
    both(patch, niedrig={'modellname': 'gpt-neu', 'foundry': '1'})
    assert 'niedrig: gpt-neu über Foundry 1 (alt.example), ohne Kostensatz' in ai.endpoint_overview()


def test_one_foundry_alone_keeps_working(setup):
    _, _, patch = setup
    ai_env(patch)
    assert L.ai_status() == {'configured': True, 'host': 'example.com', 'model': 'test'}
    assert L.ai_settings('niedrig')['url'] == 'https://example.com/responses'


def test_old_model_names_in_the_parent_choice_become_tiers(env):
    """Die Felder hielten bis 0.82 einen Modellnamen. Die Migration macht daraus
    eine Stufe, sonst zeigte die Elternwahl nach dem Update ins Leere."""
    from contextlib import closing
    from backend import db
    with closing(db.webapp_conn()) as c, c:
        ai.init_config(c)
        c.execute("UPDATE mentor_ai_config SET opening_model='gpt-5.6-terra', sources_model='gpt-4.1-alt' WHERE id=1")
        c.execute("DELETE FROM schema_meta WHERE key='migration:mentor_ai_config_003_tiers'")
    db.init_webapp_db()
    with closing(db.webapp_conn()) as c:
        row = c.execute('SELECT opening_model,sources_model FROM mentor_ai_config WHERE id=1').fetchone()
    # terra ist die mittlere Stufe; ein Name ohne Entsprechung heißt „wie das Hauptgespräch".
    assert (row['opening_model'], row['sources_model']) == ('mittel', None)


def test_the_views_still_render_without_any_foundry(setup):
    """Ohne eingerichtete Plattform bleibt die App bedienbar: Die Übersichten
    fragen nur, ob ein Mikrofon angeboten werden kann. Erst der wirkliche
    Aufruf scheitert mit Meldung. Anlass: 0.83.0 gab hier 503 zurück."""
    client, _, patch = setup
    patch.setenv('LEARNING_AI_PLATFORMS', '{}')
    assert ai.transcribe_url() == ''
    r = client.get(B)
    assert r.status_code == 200, r.text
    assert r.json()['speech'] is False
    assert r.json()['budget']['rate_available'] is True
    with pytest.raises(ai.HTTPException) as exc:
        ai.settings_for('hoch')
    assert exc.value.status_code == 503


def test_a_rejected_request_releases_its_reservation(setup):
    """404 oder falscher Schlüssel kosten kein Token. Die Reservierung stehen zu
    lassen bindet Buchwert für nichts (D89); Zeitüberschreitung bleibt stehen,
    dort kann das Modell gelaufen sein."""
    _, _, patch = setup
    both(patch)
    key = ai.reserve(1, 'mentor', None, 1000, 100)
    ai.release(key, 'nicht angenommen (404)')
    from contextlib import closing
    from backend import db
    with closing(db.webapp_conn()) as c:
        row = c.execute('SELECT status,charged_micro FROM mentor_ai_calls WHERE id=?', (key,)).fetchone()
        assert (row['status'], row['charged_micro']) == ('released', 0)
        assert ai.effective_sum(c, 'id=?', (key,)) == 0
    # Eine unklare Antwort bleibt dagegen mit ihrer Reservierung stehen.
    other = ai.reserve(1, 'mentor', None, 1000, 100)
    ai.settle(other, error='provider_error')
    with closing(db.webapp_conn()) as c:
        assert ai.effective_sum(c, 'id=?', (other,)) > 0


def test_a_crashed_call_stops_binding_budget_after_an_hour(setup):
    _, _, patch = setup
    both(patch)
    key = ai.reserve(1, 'mentor', None, 1000, 100)
    from contextlib import closing
    from backend import db
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE mentor_ai_calls SET created_at='2026-09-11T10:00:00+02:00' WHERE id=?", (key,))
    patch.setattr(ai, 'now_iso', lambda: '2026-09-11T14:00:00+02:00')
    ai.release_stale()
    with closing(db.webapp_conn()) as c:
        assert c.execute('SELECT status FROM mentor_ai_calls WHERE id=?', (key,)).fetchone()[0] == 'released'


def test_the_month_is_projected_and_warns_before_it_is_reached(setup):
    """Gewarnt wird auf die Hochrechnung hin, nicht erst beim Erreichen."""
    _, _, patch = setup
    both(patch)
    from contextlib import closing
    from backend import db
    with closing(db.webapp_conn()) as c, c:
        ai.init_config(c)
        c.execute('UPDATE mentor_ai_config SET monthly_micro=400000000, warning_micro=60000000 WHERE id=1')
        # 21 Euro in der laufenden Woche, am 11. des Monats. Ein einzelner
        # schwerer Tag wird über das Fenster geglättet, sonst würde ein
        # einmaliges Einlesen den Rest des Monats hochrechnen.
        for n in range(7):
            c.execute("INSERT INTO mentor_ai_calls(id,account_id,session_id,purpose,month,day,model,status,"
                      "reserved_micro,charged_micro,input_rate,output_rate,created_at) "
                      "VALUES(?,1,NULL,'mentor','2026-09',?,'test','settled',?,?,10,45,'now')",
                      (f'p{n}', f'2026-09-{5+n:02d}', 3_000_000, 3_000_000))
    s = ai.status()
    assert s['used_eur'] == 21.0
    # 3 Euro am Tag, 19 Tage Rest: die Hochrechnung reißt die Schwelle von 60.
    assert s['per_day_eur'] == 3.0 and s['projected_eur'] == 78.0
    assert s['warning'] is True and s['used_eur'] < 60, 'die Warnung kommt vor dem Erreichen'
