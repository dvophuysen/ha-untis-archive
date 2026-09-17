"""Spracheingabe: Aufnahme → eigene Erkennung → Text zum Prüfen, mit Budget."""
import json
import sys
from contextlib import closing
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from test_learning import env, seed, child, P, path  # noqa: F401
from test_mentor import setup, start, B  # noqa: F401
from backend import db, ai_gateway as ai
from backend.routers import mentor as m


def fake_azure(patch, calls, payload=None, status=200):
    class FakeClient:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            body = payload if payload is not None else {"text": "servi", "usage": {"input_tokens": 300, "output_tokens": 4}}
            return httpx.Response(status, json=body, request=httpx.Request("POST", url))
    patch.setattr(ai.httpx, "AsyncClient", FakeClient)


def test_url_is_derived_from_the_resource_of_its_own_tier(setup):
    client, state, patch = setup
    from test_learning import ai_env
    assert ai.transcribe_url() == "https://example.com/openai/deployments/gpt-4o-transcribe/audio/transcriptions?api-version=2025-03-01-preview"
    # Der Bereitstellungsname geht in den Pfad, nicht der Modellname.
    ai_env(patch, tiers={"transkription": {"modellname": "gpt-4o-transcribe", "bereitstellungsname": "whisper-eu", "foundry": "1"}})
    assert "/deployments/whisper-eu/" in ai.transcribe_url()
    # Zieht die Spracheingabe allein auf die zweite Foundry, folgt die Adresse ihr.
    ai_env(patch, second={"url": "https://neu.example/openai/v1/responses", "key": "neu"},
           tiers={"transkription": {"modellname": "gpt-4o-transcribe", "foundry": "2"}})
    assert ai.transcribe_url().startswith("https://neu.example/openai/deployments/gpt-4o-transcribe/")


def test_language_follows_the_subject_and_latin_gets_none():
    assert m.speech_language("Deutsch") == "de" and m.speech_language("ENGLISCH") == "en"
    assert m.speech_language("Spanisch") == "es" and m.speech_language("Mathematik") == "de"
    assert m.speech_language("LATEIN") is None and m.speech_language("Deutsch", "en") == "en"
    assert m.speech_language("Deutsch", "la") is None


def test_transcribe_sends_prompt_and_language_and_charges_the_budget(setup):
    client, state, patch = setup
    s = start(client)
    calls = []
    fake_azure(patch, calls)
    r = client.post(B + f"/sessions/{s['id']}/transcribe", data={"seconds": "4"},
                    files={"file": ("aufnahme", b"\x00" * 3000, "audio/mp4")})
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "servi", "language": "de"}
    call = calls[0]
    assert call["url"].endswith("/deployments/gpt-4o-transcribe/audio/transcriptions?api-version=2025-03-01-preview")
    assert call["data"]["language"] == "de" and call["data"]["model"] == "gpt-4o-transcribe"
    assert "Schulfach Deutsch" in call["data"]["prompt"] and "Adjektive" in call["data"]["prompt"]
    assert call["files"]["file"][0] == "aufnahme.m4a" and call["files"]["file"][2] == "audio/mp4"
    assert call["headers"] == {"api-key": "fake"}
    with closing(db.webapp_conn()) as c:
        row = c.execute("SELECT model,status,charged_micro,session_id,purpose FROM mentor_ai_calls ORDER BY created_at DESC LIMIT 1").fetchone()
    assert tuple(row) == ("gpt-4o-transcribe", "settled", 300 * 6.5 + 4 * 11.0, s["id"], "mentor")


def test_missing_usage_charges_the_estimate_and_errors_do_not_lose_the_text_path(setup):
    client, state, patch = setup
    s = start(client)
    calls = []
    fake_azure(patch, calls, payload={"text": "der Hund"})
    r = client.post(B + f"/sessions/{s['id']}/transcribe", data={"seconds": "3"}, files={"file": ("a", b"\x00" * 2000, "audio/webm")})
    assert r.status_code == 200 and r.json()["text"] == "der Hund"
    with closing(db.webapp_conn()) as c:
        row = c.execute("SELECT status,input_tokens FROM mentor_ai_calls ORDER BY created_at DESC LIMIT 1").fetchone()
    assert row["status"] == "settled" and row["input_tokens"] == 3 * ai.AUDIO_TOKENS_PER_SECOND + len(calls[0]["data"]["prompt"].encode()) // 2 + 64
    fake_azure(patch, calls, payload={"error": "boom"}, status=500)
    r = client.post(B + f"/sessions/{s['id']}/transcribe", data={"seconds": "3"}, files={"file": ("a", b"\x00" * 2000, "audio/webm")})
    assert r.status_code == 502 and "tippen" in r.json()["detail"]
    # Zu groß: abgelehnt, bevor Geld fließt.
    r = client.post(B + f"/sessions/{s['id']}/transcribe", data={"seconds": "3"}, files={"file": ("a", b"\x00" * (ai.TRANSCRIBE_MAX_BYTES + 5), "audio/webm")})
    assert r.status_code == 413


def test_spoken_flag_reaches_the_mentor_and_the_verlauf(setup):
    client, state, patch = setup
    from test_mentor import mock, send, reply
    s = start(client)
    contexts = []
    mock(patch, [reply()], contexts)
    r = send(client, s, text="Der Hund läuft", spoken=True)
    assert r.status_code == 200, r.text
    assert contexts[-1]["incoming"]["spoken"] is True
    assert [msg["payload"].get("spoken") for msg in r.json()["messages"] if msg["role"] == "user"][-1] is True
    assert "Spracheingabe" in m.INSTRUCTION
