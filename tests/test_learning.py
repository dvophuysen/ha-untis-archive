"""Integration tests for learning ownership, persistence, scheduling and AI boundary."""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "schul_cockpit"))
from backend import db, learning
from backend.auth import CurrentUser, get_current_user
from backend.routers import learning as routes
from backend.routers import afternoon

P = {"school_year": "2026/2027", "grade": 6, "region": "Niedersachsen", "school_type": "Gymnasium"}
A = {
    "operator": "Erkläre",
    "prompt": "Warum passt dieser Schritt?",
    "solution": "Weil die Regel gilt.",
    "criteria": "Regel nennen und auf das Beispiel beziehen.",
    "hint": "Welche Regel kennst du?",
    "published": True,
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    history = tmp_path / "history.db"
    with sqlite3.connect(history) as conn:
        conn.executescript(
            "CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,entry_id TEXT); INSERT INTO accounts VALUES(1,'Test A','entry-a'),(2,'Test B','entry-b');"
        )
    monkeypatch.setattr(
        db,
        "SETTINGS",
        SimpleNamespace(webapp_db_path=tmp_path / "webapp.db", history_db_path=history),
    )
    db.init_webapp_db()
    with closing(db.webapp_conn()) as conn:
        for uid, role in [(1, "parent"), (2, "child"), (3, "child"), (4, "parent")]:
            conn.execute(
                "INSERT INTO users(id,ha_user_id,role,display_name,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                (uid, f"test-{uid}", role, "Test", "now", "now"),
            )
        conn.executescript(
            "INSERT INTO user_account_links VALUES(1,1,1),(1,2,1),(2,1,1),(3,2,1),(4,1,0);"
        )
    state = SimpleNamespace(user=CurrentUser(1, "test-1", "Test", "parent", False, "pin"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    monkeypatch.setattr(routes, "today_local", lambda: date(2026, 9, 11))
    monkeypatch.setattr(routes, "now_iso", lambda: "2026-09-11T15:00:00+02:00")
    monkeypatch.setattr(
        afternoon, "_budget_for_today", lambda account, day: (60, {"source": "test"})
    )

    async def exams(*a, **kw):
        return {"exams": [], "calendar_error": None}

    monkeypatch.setattr(routes, "resolve_exams", exams)
    with TestClient(app) as client:
        yield client, state, monkeypatch


def path(account=1):
    return f"/api/accounts/{account}/learning"


def seed(client, account=1, **extra):
    p = client.put(path(account) + "/profiles", json={**P, **extra})
    assert p.status_code == 200, p.text
    t = client.post(
        path(account) + "/topics",
        json={
            "profile_id": p.json()["id"],
            "subject": "Deutsch",
            "title": "Argumentieren",
            "objective": "Ich kann eine Aussage begründen.",
        },
    )
    assert t.status_code == 200, t.text
    a = client.post(path(account) + f"/topics/{t.json()['id']}/activities", json=A)
    assert a.status_code == 200, a.text
    return p.json()["id"], t.json()["id"], a.json()["id"]


def child(state, uid=2):
    state.user = CurrentUser(uid, f"test-{uid}", "Test", "child", False, "pin")


def test_migrations_idempotent_and_backup_keeps_material_blob(env, tmp_path):
    client, state, _ = env
    _, tid, _ = seed(client)
    mid = client.post(path() + f"/topics/{tid}/materials", json={"title": "Blatt"}).json()["id"]
    image = b"\x89PNG\r\n\x1a\nfixture"
    assert (
        client.put(
            path() + f"/materials/{mid}/file", files={"file": ("blatt.png", image, "image/png")}
        ).status_code
        == 200
    )
    db.init_webapp_db()
    with closing(db.webapp_conn()) as src, sqlite3.connect(tmp_path / "backup.db") as dst:
        src.backup(dst)
    with sqlite3.connect(tmp_path / "backup.db") as c:
        assert c.execute("SELECT file_bytes FROM learning_materials").fetchone()[0] == image


def test_child_isolation_and_read_only_parent(env):
    client, state, _ = env
    _, tid, aid = seed(client)
    child(state, 3)
    for suffix in ["", f"/topics/{tid}", f"/activities/{aid}/start"]:
        response = (
            client.post(path() + suffix)
            if suffix.endswith("/start")
            else client.get(path() + suffix)
        )
        assert response.status_code == 403
    assert client.get(path(2) + f"/topics/{tid}").status_code == 404
    child(state)
    assert client.put(path() + "/profiles", json=P).status_code == 403
    assert client.get(path() + "/export").status_code == 403
    state.user = CurrentUser(4, "test-4", "Read only", "parent", False, "pin")
    assert client.get(path()).status_code == 200
    assert client.post(path() + f"/activities/{aid}/start").status_code == 403


def test_sessions_hide_answers_until_attempt_help_is_persistent(env):
    client, state, _ = env
    _, tid, aid = seed(client)
    child(state)
    detail = client.get(path() + f"/topics/{tid}").json()
    assert "solution" not in detail["activities"][0]
    r = client.post(path() + f"/activities/{aid}/start").json()
    sid = r["session"]["id"]
    assert "solution" not in r["activity"] and "hint" not in r["activity"]
    assert (
        client.post(
            path() + f"/sessions/{sid}/finish", json={"outcome": "independent", "minutes": 5}
        ).status_code
        == 409
    )
    assert client.post(path() + f"/activities/{aid}/start").json()["session"]["id"] == sid
    assert client.post(path() + f"/sessions/{sid}/help").json()["session"]["help_used"] == 1
    r = client.post(path() + f"/sessions/{sid}/answer", json={"answer": "Mein Versuch"}).json()
    assert r["activity"]["solution"] == A["solution"]
    assert (
        client.post(path() + f"/sessions/{sid}/answer", json={"answer": "Neue Antwort"}).status_code
        == 409
    )
    end = client.post(
        path() + f"/sessions/{sid}/finish", json={"outcome": "independent", "minutes": 5}
    )
    assert end.status_code == 200
    assert client.post(
        path() + f"/sessions/{sid}/finish", json={"outcome": "independent", "minutes": 5}
    ).json()["already_completed"]
    with closing(db.webapp_conn()) as c:
        r = c.execute("SELECT * FROM learning_reviews").fetchone()
        assert r["streak"] == 0 and r["last_outcome"] == "partly" and r["next_due"] == "2026-09-12"


def test_other_child_cannot_read_material_or_session(env):
    client, state, _ = env
    _, tid, aid = seed(client)
    mid = client.post(path() + f"/topics/{tid}/materials", json={"title": "Blatt"}).json()["id"]
    child(state)
    sid = client.post(path() + f"/activities/{aid}/start").json()["session"]["id"]
    child(state, 3)
    assert client.get(path(2) + f"/sessions/{sid}").status_code == 404
    assert client.get(path(2) + f"/materials/{mid}/file").status_code == 404
    assert (
        client.put(
            path(2) + f"/materials/{mid}/file", files={"file": ("f.png", b"\x89PNG\r\n\x1a\ndata")}
        ).status_code
        == 404
    )


def test_school_year_rollover_keeps_history_and_pauses_old_topics(env):
    client, _, _ = env
    _, tid, aid = seed(client)
    assert client.get(path()).json()["today"]["activities"]
    p2 = client.put(
        path() + "/profiles", json={**P, "school_year": "2027/2028", "grade": 7}
    ).json()["id"]
    r = client.get(path()).json()
    assert len(r["profiles"]) == 2 and sum(p["active"] for p in r["profiles"]) == 1
    assert r["topics"][0]["id"] == tid and not r["topics"][0]["current_year"]
    assert r["today"]["activities"] == []
    # Moving a historical topic would silently relabel its old results.
    assert (
        client.put(
            path() + f"/topics/{tid}",
            json={"profile_id": p2, "subject": "Deutsch", "title": "A", "objective": "B"},
        ).status_code
        == 422
    )


def test_daily_budget_reserves_homework_and_zero_means_pause(env):
    client, _, _ = env
    seed(client, daily_minutes=15)
    with closing(db.webapp_conn()) as c:
        c.execute(
            "INSERT INTO tasks(account_id,title,source,due_date,estimated_minutes,created_at,updated_at) VALUES(1,'Hausaufgabe','manual','2026-09-12',60,'now','now')"
        )
    assert client.get(path()).json()["today"]["activities"] == []
    with closing(db.webapp_conn()) as c:
        c.execute("DELETE FROM tasks")
    client.put(path() + "/profiles", json={**P, "daily_minutes": 0})
    assert client.get(path()).json()["today"]["activities"] == []


def test_completion_consumes_daily_cap_without_refill(env):
    client, state, _ = env
    _, tid, aid = seed(client, daily_minutes=5, max_sessions=1)
    client.post(path() + f"/topics/{tid}/activities", json={**A, "prompt": "Zweite Aufgabe"})
    child(state)
    sid = client.post(path() + f"/activities/{aid}/start").json()["session"]["id"]
    client.post(path() + f"/sessions/{sid}/answer", json={"answer": "Antwort"})
    client.post(path() + f"/sessions/{sid}/finish", json={"outcome": "independent", "minutes": 5})
    r = client.get(path()).json()["today"]
    assert r["completed_sessions"] == 1 and r["activities"] == []


def test_snapshot_does_not_change_mid_session(env):
    client, state, _ = env
    _, _, aid = seed(client)
    sid = client.post(path() + f"/activities/{aid}/start").json()["session"]["id"]
    client.put(path() + f"/activities/{aid}", json={**A, "solution": "Geänderte Lösung"})
    r = client.post(path() + f"/sessions/{sid}/answer", json={"answer": "Antwort"}).json()
    assert r["activity"]["solution"] == A["solution"]
    client.post(path() + f"/sessions/{sid}/finish", json={"outcome": "independent", "minutes": 5})
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT COUNT(*) FROM learning_reviews").fetchone()[0] == 0


def test_material_verification_upload_and_content_type(env):
    client, state, _ = env
    _, tid, _ = seed(client)
    mid = client.post(
        path() + f"/topics/{tid}/materials",
        json={"title": "Quelle", "content_text": "Alter Text", "verified": True},
    ).json()["id"]
    assert (
        client.put(
            path() + f"/materials/{mid}/file",
            files={"file": ("evil.html", b"<html>bad</html>", "image/png")},
        ).status_code
        == 415
    )
    assert (
        client.put(
            path() + f"/materials/{mid}/file",
            files={"file": ("blatt.pdf", b"%PDF-1.4 test", "application/pdf")},
        ).status_code
        == 200
    )
    m = client.get(path() + f"/topics/{tid}").json()["materials"][0]
    assert not m["verified"] and m["content_text"] == ""
    child(state)
    mid2 = client.post(
        path() + f"/topics/{tid}/materials", json={"title": "Kind", "verified": True}
    ).json()["id"]
    with closing(db.webapp_conn()) as c:
        assert (
            c.execute("SELECT verified FROM learning_materials WHERE id=?", (mid2,)).fetchone()[0]
            == 0
        )


def test_ai_missing_config_and_unknown_source_fail_without_call(env):
    client, _, monkeypatch = env
    _, tid, _ = seed(client)
    monkeypatch.delenv("LEARNING_AI_KEY", raising=False)
    assert (
        client.post(path() + f"/topics/{tid}/generate", json={"material_ids": [1]}).status_code
        == 503
    )


def test_ai_uses_selected_sources_and_always_creates_drafts(env):
    client, state, monkeypatch = env
    _, tid, _ = seed(client, ai_enabled=True)
    mid = client.post(
        path() + f"/topics/{tid}/materials",
        json={
            "title": "Geprüfte Quelle",
            "content_text": "Eine begründete Aussage braucht ein Argument.",
            "verified": True,
        },
    ).json()["id"]
    client.post(
        path() + f"/topics/{tid}/materials",
        json={
            "title": "Ungewählte Quelle",
            "content_text": "DIES DARF NICHT ÜBERTRAGEN WERDEN",
            "verified": True,
        },
    )
    for k, v in {
        "LEARNING_AI_URL": "https://model.example/chat/completions",
        "LEARNING_AI_KEY": "fake-test-key",
        "LEARNING_AI_MODEL": "test-model",
    }.items():
        monkeypatch.setenv(k, v)
    calls = []

    class FakeClient:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append(kwargs)
            payload = {"activities": [{**A, "source_ids": [mid]}]}
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps(payload)}}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(routes.httpx, "AsyncClient", FakeClient)
    r = client.post(path() + f"/topics/{tid}/generate", json={"material_ids": [mid]})
    assert r.status_code == 200, r.text
    user_payload = json.dumps(calls[0]["json"]["messages"][1])
    assert "DIES DARF NICHT" not in user_payload and "Test A" not in user_payload
    with closing(db.webapp_conn()) as c:
        assert (
            c.execute("SELECT published FROM learning_activities WHERE origin='ai'").fetchone()[0]
            == 0
        )
    child(state)
    assert len(client.get(path() + f"/topics/{tid}").json()["activities"]) == 1


def test_id_reconciliation_moves_entire_learning_tree(env):
    client, _, _ = env
    pid, tid, _ = seed(client)
    from backend.reconcile import _apply_account_remaps

    with closing(db.webapp_conn()) as c:
        _apply_account_remaps(c, [(1, 7)])
        assert (
            c.execute("SELECT account_id FROM learning_profiles WHERE id=?", (pid,)).fetchone()[0]
            == 7
        )
        assert (
            c.execute("SELECT profile_id FROM learning_topics WHERE id=?", (tid,)).fetchone()[0]
            == pid
        )


def test_spacing_progresses_only_for_unassisted_and_resets_on_difficulty():
    day = date(2026, 9, 11)
    assert learning.next_review(0, "independent", False, day) == (1, "2026-09-13")
    assert learning.next_review(1, "independent", False, day) == (2, "2026-09-18")
    assert learning.next_review(3, "independent", True, day) == (0, "2026-09-12")
    assert learning.next_review(3, "again", False, day) == (0, "2026-09-12")


def test_carry_forward_copies_drafts_without_relabelling_old_attempts(env):
    client, _, _ = env
    _, tid, aid = seed(client)
    client.put(path() + "/profiles", json={**P, "school_year": "2027/2028", "grade": 7})
    new = client.post(path() + f"/topics/{tid}/carry-forward")
    assert new.status_code == 200, new.text
    d = client.get(path() + f"/topics/{new.json()['id']}").json()
    assert d["activities"] and not d["activities"][0]["published"]
    assert client.get(path() + f"/topics/{tid}").json()["activities"][0]["id"] == aid


def test_repeated_success_same_day_does_not_extend_spacing(env):
    client, state, _ = env
    _, _, aid = seed(client)
    child(state)
    for _ in range(2):
        sid = client.post(path() + f"/activities/{aid}/start").json()["session"]["id"]
        client.post(path() + f"/sessions/{sid}/answer", json={"answer": "Antwort"})
        assert (
            client.post(
                path() + f"/sessions/{sid}/finish", json={"outcome": "independent", "minutes": 5}
            ).status_code
            == 200
        )
    with closing(db.webapp_conn()) as c:
        r = c.execute("SELECT streak,next_due FROM learning_reviews").fetchone()
        assert tuple(r) == (1, "2026-09-13")


def test_existing_manual_budget_preserves_zero(env):
    client, _, monkeypatch = env
    with closing(db.webapp_conn()) as c:
        c.execute(
            "INSERT INTO account_settings(account_id,default_daily_budget_minutes,auto_budget,created_at,updated_at) VALUES(1,0,0,'now','now')"
        )
    # Reload original function because the fixture stubs only this boundary for the other tests.
    import importlib

    module = importlib.reload(afternoon)
    assert module._budget_for_today(1, date(2026, 9, 11))[0] == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://example.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview",
        "https://example.openai.azure.com/openai/v1/responses",
    ],
)
def test_responses_protocol(url):
    p = learning.model_payload(
        url,
        "deployment-name",
        "instructions",
        {"topic": "Test"},
        [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}],
    )
    assert p["model"] == "deployment-name" and p["store"] is False
    assert "messages" not in p
    assert p["input"][0]["content"][1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,AAAA",
    }
    r = {
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": '{"activities":[]}'}],
            },
        ],
    }
    assert learning.model_output(url, r) == '{"activities":[]}'
    for invalid in [
        {"status": "incomplete", "output": r["output"]},
        {"status": "completed", "output": []},
    ]:
        with pytest.raises(ValueError):
            learning.model_output(url, invalid)
