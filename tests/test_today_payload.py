"""Die Startseite lädt nur, was sie zeigt (D177): offene und zuletzt erledigte
Aufgaben statt der ganzen Historie."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

from test_learning import env, child  # noqa: F401
from backend import db
from backend.routers import tasks as task_routes


def test_recent_done_days_hides_old_done_tasks(env):
    client, _, _ = env
    client.app.include_router(task_routes.router, prefix="/api")
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=40)).isoformat()
    fresh = (now - timedelta(days=2)).isoformat()
    with closing(db.webapp_conn()) as c, c:
        for title, status, done_at in (("offen", "open", None), ("frisch", "done", fresh), ("alt", "done", old)):
            c.execute("INSERT INTO tasks(account_id,title,task_type,status,source,created_at,updated_at,completed_at)"
                      " VALUES(1,?,'homework',?,'manual',?,?,?)", (title, status, old, old, done_at))
    full = {t["title"] for t in client.get("/api/accounts/1/tasks").json()["tasks"]}
    slim = {t["title"] for t in client.get("/api/accounts/1/tasks?recent_done_days=14").json()["tasks"]}
    assert {"offen", "frisch", "alt"} <= full
    assert "offen" in slim and "frisch" in slim and "alt" not in slim
