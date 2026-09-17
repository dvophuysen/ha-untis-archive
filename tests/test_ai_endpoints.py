"""Zwei Foundry-Zugänge nebeneinander: jedes Deployment über den zugeordneten (D87)."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path  # noqa: F401
from test_mentor import setup, start, reply, B  # noqa: F401
from backend import ai_gateway as ai, learning as L

FIRST = 'https://alt.example/openai/v1/responses'
SECOND = 'https://neu.example/openai/v1/responses'


def two_foundries(patch, models_2='test-luna'):
    patch.setenv('LEARNING_AI_URL', FIRST)
    patch.setenv('LEARNING_AI_KEY', 'schluessel-alt')
    patch.setenv('LEARNING_AI_URL_2', SECOND)
    patch.setenv('LEARNING_AI_KEY_2', 'schluessel-neu')
    patch.setenv('LEARNING_AI_MODELS_2', models_2)
    patch.setitem(ai.RATES, 'test-luna', (1.9, 9.0))


def test_names_survive_every_shape_bashio_hands_over(monkeypatch):
    assert L.deployment_names('a,b') == ('a', 'b')
    assert L.deployment_names('a\nb\n') == ('a', 'b')
    assert L.deployment_names(' a , a ,b,') == ('a', 'b')
    # Eine Listenoption kommt als JSON, kompakt oder über mehrere Zeilen.
    assert L.deployment_names('["a","b"]') == ('a', 'b')
    assert L.deployment_names('[\n  "a",\n  "b"\n]') == ('a', 'b')
    # Nicht gesetzt: bashio schreibt "null", das ist kein Deployment.
    assert L.deployment_names('null') == () and L.deployment_names('') == ()
    assert L.deployment_names('[]') == ()


def test_only_listed_deployments_move_to_the_second_access(setup):
    _, _, patch = setup
    two_foundries(patch)
    assert L.ai_endpoint('test') == (FIRST, 'schluessel-alt')
    assert L.ai_endpoint('test-luna') == (SECOND, 'schluessel-neu')


def test_a_listed_deployment_never_falls_back_to_the_old_resource(setup):
    _, _, patch = setup
    two_foundries(patch)
    patch.setenv('LEARNING_AI_URL_2', '')
    with pytest.raises(L.AiEndpointMissing):
        L.ai_endpoint('test-luna')
    # Der Gateway macht daraus eine lesbare Meldung, keinen Aufruf an die alte Adresse.
    with pytest.raises(ai.HTTPException) as exc:
        ai.endpoint_for('test-luna')
    assert exc.value.status_code == 503 and 'zweite' in exc.value.detail


def test_the_turn_uses_the_key_of_the_resource_it_calls(setup):
    client, _, patch = setup
    two_foundries(patch)
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
                                'content': [{'type': 'output_text', 'text': __import__('json').dumps(reply())}]}]}
            return httpx.Response(200, json=body, request=httpx.Request('POST', url))
    patch.setattr(ai.httpx, 'AsyncClient', FakeClient)

    r = client.post(B + f"/sessions/{session['id']}/turn",
                    json={'text': 'Ich fange an.', 'request_key': 'zug-eins-1', 'version': session['version'], 'kind': 'message'})
    assert r.status_code == 200, r.text
    assert calls[0] == {'url': FIRST, 'key': 'schluessel-alt', 'model': 'test'}

    # Zieht das Hauptmodell um, geht derselbe Zug an die neue Ressource.
    calls.clear()
    patch.setenv('LEARNING_AI_MODELS_2', 'test-luna,test')
    session = client.get(B + f"/sessions/{session['id']}").json()
    r = client.post(B + f"/sessions/{session['id']}/turn",
                    json={'text': 'Weiter.', 'request_key': 'zug-zwei-2', 'version': session['version'], 'kind': 'message'})
    assert r.status_code == 200, r.text
    assert calls[0] == {'url': SECOND, 'key': 'schluessel-neu', 'model': 'test'}


def test_the_two_accesses_may_use_different_api_shapes(setup):
    _, _, patch = setup
    two_foundries(patch)
    patch.setenv('LEARNING_AI_URL', 'https://alt.example/openai/deployments/test/chat/completions?api-version=2024-10-21')
    assert not L.uses_responses(L.ai_endpoint('test')[0])
    assert L.uses_responses(L.ai_endpoint('test-luna')[0])


def test_the_transcription_address_follows_its_own_deployment(setup):
    _, _, patch = setup
    two_foundries(patch, models_2='gpt-4o-transcribe')
    assert ai.transcribe_url().startswith('https://neu.example/openai/deployments/gpt-4o-transcribe/')
    patch.setenv('LEARNING_AI_MODELS_2', 'test-luna')
    assert ai.transcribe_url().startswith('https://alt.example/openai/deployments/gpt-4o-transcribe/')


def test_speech_sends_the_key_of_its_own_resource(setup):
    client, _, patch = setup
    two_foundries(patch, models_2='gpt-4o-transcribe')
    session = start(client)
    calls = []

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, **kwargs):
            calls.append({'url': url, 'key': kwargs['headers']['api-key']})
            return httpx.Response(200, json={'text': 'hallo', 'usage': {'input_tokens': 80, 'output_tokens': 4}},
                                  request=httpx.Request('POST', url))
    patch.setattr(ai.httpx, 'AsyncClient', FakeClient)
    patch.setitem(ai.RATES, 'gpt-4o-transcribe', (6.5, 11.0))

    r = client.post(B + f"/sessions/{session['id']}/transcribe", data={'seconds': '3'},
                    files={'file': ('aufnahme', b'\x00' * 3000, 'audio/mp4')})
    assert r.status_code == 200, r.text
    assert calls[0]['url'].startswith('https://neu.example/') and calls[0]['key'] == 'schluessel-neu'


def test_status_and_log_report_the_resource_that_serves_the_main_model(setup):
    _, _, patch = setup
    two_foundries(patch, models_2='test')
    assert L.ai_status() == {'configured': True, 'host': 'neu.example', 'model': 'test'}
    overview = ai.endpoint_overview()
    assert 'test: neu.example' in overview and 'gpt-4o-transcribe: alt.example' in overview
    # Fehlt der zweite Zugang, sagt es die Zeile, statt die alte Adresse zu nennen.
    patch.setenv('LEARNING_AI_KEY_2', '')
    assert L.ai_status()['configured'] is False
    assert 'test: zweiter Zugang nicht eingerichtet' in ai.endpoint_overview()


def test_a_single_access_keeps_working_unchanged(setup):
    _, _, patch = setup
    patch.delenv('LEARNING_AI_URL_2', raising=False)
    patch.delenv('LEARNING_AI_MODELS_2', raising=False)
    assert L.ai_endpoint('test') == ('https://example.com/responses', 'fake')
    assert L.ai_status() == {'configured': True, 'host': 'example.com', 'model': 'test'}
