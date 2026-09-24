"""Eine in HA erledigte Untis-Aufgabe lässt sich in der App wieder öffnen.
Bis 1.13.24 öffnete die App nur ihre eigene Zeile; der Abgleich danach sah
„in HA erledigt, in der App offen“, ließ HA gewinnen, und die Aufgabe war
sofort wieder erledigt."""
from contextlib import closing

from test_learning import env, child  # noqa: F401
from backend import db, sync_worker
from backend.routers import tasks as task_routes

ENTITY = "todo.hausaufgaben_test"
UID = "uid-de-1"


class FakeSupervisor:
    available = True

    def __init__(self, fail=False):
        self.items = [{"uid": UID, "summary": "Deutsch", "status": "completed", "due": "2026-09-25",
                       "description": "AB, Aufgabe 3a [DE051516]"}]
        self.updates = []
        self.fail = fail

    async def get_todo_items(self, entity_id):
        return [dict(i) for i in self.items]

    async def update_todo_item(self, entity_id, item, *, status=None, rename=None):
        if self.fail:
            raise sync_worker.SupervisorError("HA nicht erreichbar")
        self.updates.append((entity_id, item, status))
        for i in self.items:
            if i["uid"] == item and status:
                i["status"] = status


def _setup(client, patch, fail=False):
    client.app.include_router(task_routes.router, prefix="/api")
    sup = FakeSupervisor(fail)
    patch.setattr(sync_worker, "get_supervisor", lambda: sup)
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO account_todo_lists(account_id,ha_entity_id,updated_at) VALUES(1,?, 'now')", (ENTITY,))
        task_id = c.execute(
            "INSERT INTO tasks(account_id,ha_uid,title,task_type,status,due_date,notes,source,created_at,updated_at,completed_at)"
            " VALUES(1,?,'Deutsch','homework','done','2026-09-25','AB, Aufgabe 3a [DE051516]','ha_todo','now','now','now')",
            (UID,)).lastrowid
    return sup, task_id


def _status(task_id):
    with closing(db.webapp_conn()) as c:
        return c.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0]


def test_reopening_a_task_done_in_ha_keeps_it_open(env):
    client, _, patch = env
    sup, task_id = _setup(client, patch)
    r = client.patch(f"/api/tasks/{task_id}", json={"status": "open"})
    assert r.status_code == 200, r.text
    assert (ENTITY, UID, "needs_action") in sup.updates
    assert _status(task_id) == "open"


def test_if_ha_refuses_the_task_stays_done_and_says_so(env):
    client, _, patch = env
    sup, task_id = _setup(client, patch, fail=True)
    r = client.patch(f"/api/tasks/{task_id}", json={"status": "open"})
    assert r.status_code == 502 and "bleibt erledigt" in r.json()["detail"]
    assert _status(task_id) == "done"
