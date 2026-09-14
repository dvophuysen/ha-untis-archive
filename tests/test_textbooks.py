from contextlib import closing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_learning import child, env
from backend import db
from backend.auth import get_current_user
from backend.routers import textbooks


URL = "/api/accounts/1/textbooks"


def setup(env):
    client, state, patch = env
    app = FastAPI()
    app.include_router(textbooks.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state.user
    patch.setattr(textbooks, "webapp_conn", db.webapp_conn)
    with TestClient(app) as isolated:
        yield isolated, state


def test_parent_can_store_update_and_delete_write_only_credentials(env):
    for client, _ in setup(env):
        initial = client.get(URL).json()
        assert initial == {
            "configured": False,
            "portal_url": "https://gaw-iserv.de",
            "username": "",
            "password_saved": False,
            "verified_at": None,
            "verification_status": None,
            "updated_at": None,
        }
        saved = client.put(URL, json={
            "portal_url": "https://gaw-iserv.de/",
            "username": "noah",
            "password": "very-secret",
        })
        assert saved.status_code == 200
        assert "password_ciphertext" not in saved.json() and "very-secret" not in saved.text
        assert saved.json()["password_saved"] is True
        with closing(db.webapp_conn()) as conn:
            raw = conn.execute(
                "SELECT password_ciphertext FROM digital_textbook_credentials WHERE account_id=1"
            ).fetchone()[0]
        assert raw != "very-secret" and "very-secret" not in raw

        changed = client.put(URL, json={
            "portal_url": "https://gaw-iserv.de",
            "username": "noah-neu",
            "password": None,
        })
        assert changed.status_code == 200
        with closing(db.webapp_conn()) as conn:
            assert conn.execute(
                "SELECT password_ciphertext FROM digital_textbook_credentials WHERE account_id=1"
            ).fetchone()[0] == raw
        assert client.delete(URL).status_code == 204
        assert client.get(URL).json()["configured"] is False


def test_credentials_are_parent_only_and_validate_portal(env):
    for client, state in setup(env):
        for bad in ("http://gaw-iserv.de", "https://evil.example", "https://user:pw@gaw-iserv.de"):
            assert client.put(URL, json={"portal_url": bad, "username": "x", "password": "y"}).status_code == 422
        child(state)
        assert client.get(URL).status_code == 403
        assert client.put(URL, json={
            "portal_url": "https://gaw-iserv.de", "username": "x", "password": "y"
        }).status_code == 403
