"""Die Kiosk-Anmeldung listet alle, die sich mit PIN anmelden dürfen. Bis
1.13.20 fragte sie nach der Rolle „kid“, die es nicht gibt; die Kinder
(Rolle „child“) standen nicht in der Auswahl."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import db, pin_auth
from backend.routers import kiosk


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db, "SETTINGS",
        SimpleNamespace(webapp_db_path=tmp_path / "webapp.db", history_db_path=tmp_path / "h.db"),
    )
    db.init_webapp_db()
    with db.webapp_conn() as c:
        for uid, name, role in (("k1", "Kind A", "child"), ("p1", "Elternteil", "parent"),
                                ("x1", "Wartend", "pending"), ("k2", "Kind ohne PIN", "child")):
            c.execute("INSERT INTO users (ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
                      "VALUES (?, ?, ?, 0, 'x', 'x')", (uid, name, role))
        for user_id in (1, 2, 3):
            pin_auth.set_pin(c, user_id, "4711")
    app = FastAPI()
    app.include_router(kiosk.router)
    return TestClient(app)


def test_children_with_a_pin_are_offered_at_the_kiosk(client):
    page = client.get("/kiosk/login").text
    assert "Kind A" in page and "Elternteil" in page
    assert "Wartend" not in page and "Kind ohne PIN" not in page
