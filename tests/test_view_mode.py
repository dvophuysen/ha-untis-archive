"""Wer benutzt das Gerät (D175): Mitlesen schreibt nie, der Testmodus sperrt
Lernverlauf und nimmt die Tasche beim Beenden zurück."""
from contextlib import closing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_learning import env, child  # noqa: F401
from backend import audit, db, view_mode
from backend.auth import CurrentUser, get_current_user
from backend.routers import audit as audit_routes, tasks as task_routes


def _app(user):
    app = FastAPI()
    app.middleware("http")(view_mode.middleware)
    app.include_router(task_routes.router, prefix="/api")
    app.include_router(audit_routes.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_mirror_blocks_every_write_but_reads(env):
    client = _app(CurrentUser(1, "test-1", "Test", "parent", False, "pin"))
    h = {"x-view-mode": "mirror"}
    assert client.get("/api/accounts/1/tasks", headers=h).status_code == 200
    r = client.post("/api/accounts/1/tasks", json={"title": "Nicht anlegen"}, headers=h)
    assert r.status_code == 403 and "Nur ansehen" in r.json()["detail"]
    assert client.post("/api/accounts/1/tasks", json={"title": "Anlegen"}).status_code == 201


def test_test_mode_blocks_learning_history(env):
    client = _app(CurrentUser(1, "test-1", "Test", "parent", True, "pin"))
    r = client.post("/api/accounts/1/learning/mentor/sessions", json={}, headers={"x-view-mode": "test"})
    assert r.status_code == 403 and "Testmodus" in r.json()["detail"]


def test_packing_changes_in_test_mode_are_reverted(env):
    user = CurrentUser(1, "test-1", "Test", "parent", True, "pin")
    client = _app(user)
    with closing(db.webapp_conn()) as c, c:
        c.execute("UPDATE users SET demo_mode=1 WHERE id=1")
        c.execute("INSERT INTO packing_items VALUES(1,'2026-09-25','subject:ma',0,1,'t0',NULL)")
        before = dict(c.execute("SELECT * FROM packing_items").fetchone())
        c.execute("UPDATE packing_items SET done=1, revision=2, updated_at='t1', confirmed_by=1")
        after = dict(c.execute("SELECT * FROM packing_items").fetchone())
        audit.log(c, user_id=1, account_id=1, op_type="update", target_kind="packing", target_id=None, before=before, after=after)
        c.execute("INSERT INTO packing_items VALUES(1,'2026-09-25','subject:de',1,1,'t1',1)")
        new = dict(c.execute("SELECT * FROM packing_items WHERE item_key='subject:de'").fetchone())
        audit.log(c, user_id=1, account_id=1, op_type="insert", target_kind="packing", target_id=None, after=new)
    assert client.post("/api/my-changes/revert-all-demo").json()["reverted"] == 2
    with closing(db.webapp_conn()) as c:
        rows = {r["item_key"]: r["done"] for r in c.execute("SELECT * FROM packing_items")}
    assert rows == {"subject:ma": 0}
