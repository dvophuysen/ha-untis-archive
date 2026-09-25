"""Eigene Eltern-Hülle (D183): „Erledigen“, Rechte je Gerätezustand, Usage-Ping.

Mitlesen und Kindmodus gelten auf dem Server als Kind: keine Eltern-Werkzeuge,
keine Eltern-Einstellungen, die Nutzung zählt für das Kind."""
from contextlib import closing
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_learning import env, child  # noqa: F401
from backend import audit, db, parent_todo, view_mode
from backend import materials as store
from backend.auth import CurrentUser, get_current_user
from backend.routers import (audit as audit_routes, materials as material_routes, mentor as mentor_routes,
                             parent_todo as todo_routes, reminders as reminder_routes, settings_router, usage as usage_routes)

PARENT = CurrentUser(1, "test-1", "Test", "parent", False, "pin")
CHILD = CurrentUser(2, "test-2", "Test", "child", False, "pin")
TODAY = date(2026, 9, 11)


def _app(state):
    app = FastAPI()
    app.middleware("http")(view_mode.middleware)
    for r in (todo_routes, settings_router, audit_routes, usage_routes, material_routes, mentor_routes, reminder_routes):
        app.include_router(r.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    return TestClient(app)


def test_acts_as_parent_follows_the_device_state():
    assert view_mode.acts_as_parent(PARENT, None)
    assert view_mode.acts_as_parent(PARENT, "test")
    assert not view_mode.acts_as_parent(PARENT, "child")
    assert not view_mode.acts_as_parent(PARENT, "mirror")
    assert not view_mode.acts_as_parent(CHILD, None)
    admin = CurrentUser(9, "test-9", "Test", "pending", True, "pin")
    assert view_mode.acts_as_parent(admin, None) and not view_mode.acts_as_parent(admin, "child")


def _fake_exams(monkeypatch, entries=(), exams=()):
    async def resolve(account_id, **kw):
        return {"exams": list(exams) if account_id == 1 else [], "all_entries": list(entries) if account_id == 1 else [],
                "calendar_error": None}
    from backend import exams as exam_mod
    monkeypatch.setattr(exam_mod, "resolve_exams", resolve)


def test_todo_lists_parent_work_per_child(env, monkeypatch):
    state = {"user": PARENT}
    client = _app(state)
    soon = (TODAY + timedelta(days=5)).isoformat()
    _fake_exams(monkeypatch,
                entries=[{"source": "calendar", "status": "unmatched", "date": soon, "title": "Test Kurs 7"},
                         {"source": "calendar", "status": "auto", "date": soon, "title": "Mathe"},
                         {"source": "calendar", "status": "unmatched", "date": "2026-01-01", "title": "Alt"}],
                exams=[{"exam_key": "cal:m", "date": soon, "subject_name": "Mathematik"},
                       {"exam_key": "cal:e", "date": (TODAY + timedelta(days=40)).isoformat(), "subject_name": "Englisch"}])
    seen = []

    def exam_sources(account_id, subject, since, until):
        seen.append(subject)
        return {"missing": 3, "missing_items": [{"label": "Arbeitsheft", "pages": [12, 13, 14], "pages_label": "S. 12–14"}],
                "pending_items": [{"kind": "budget", "label": "Schulbuch", "page": 40}],
                "notice": True, "notice_id": 77, "notice_verified": False}
    monkeypatch.setattr(parent_todo.sources, "exam_sources", exam_sources)
    monkeypatch.setattr(todo_routes, "today_local", lambda: TODAY)
    monkeypatch.setattr(store, "retakes", lambda account_id, limit=10: [
        {"id": 5, "title": "Zerlegen", "source_label": "Arbeitsheft", "source_page": 20, "reason": "Das Foto ist unscharf."}]
        if account_id == 1 else [])
    monkeypatch.setattr(parent_todo, "needs_review_count", lambda account_id: 2 if account_id == 1 else 0)
    monkeypatch.setattr(parent_todo.ai, "status", lambda: {"opening_confirmed": False, "rate_available": False})

    r = client.get("/api/parent/todo")
    assert r.status_code == 200, r.text
    data = r.json()
    assert [k["name"] for k in data["kids"]] == ["Test A", "Test B"]
    kinds = {i["kind"]: i for i in data["kids"][0]["items"]}
    # Nur die Arbeit der nächsten zwei Wochen, nicht die in 40 Tagen.
    assert seen == ["Mathematik"]
    assert set(kinds) == {"missing_material", "notice_check", "budget_wait", "retake", "needs_review",
                          "calendar_assign", "learning_frame"}
    missing = kinds["missing_material"]
    assert missing["action"]["page"] == "scannen" and missing["action"]["query"] == {"acc": "1", "art": "book_page", "fach": "Mathematik"}
    assert "3 Seiten fehlen" in missing["reason"] and "S. 12–14" in missing["reason"]
    assert kinds["notice_check"]["action"]["query"] == {"material": "77"}
    assert kinds["calendar_assign"]["title"] == "1 Termin zuordnen" and kinds["calendar_assign"]["action"]["page"] == "exams"
    assert kinds["retake"]["action"] == {"label": "Neu fotografieren", "page": "materialien", "args": [], "section": "fotos", "query": {}}
    assert kinds["learning_frame"]["action"]["args"] == ["legacy"]
    assert all(i["account_id"] == 1 for i in data["kids"][0]["items"])
    # Kind B: nur der fehlende Lernrahmen.
    assert [i["kind"] for i in data["kids"][1]["items"]] == ["learning_frame"]
    assert {i["kind"] for i in data["household"]} == {"ai_opening", "ai_rates"}
    assert data["blocking"] == []
    assert data["total"] == 7 + 1 + 2


def test_todo_blocking_and_empty_state(env, monkeypatch):
    state = {"user": PARENT}
    client = _app(state)
    _fake_exams(monkeypatch)
    monkeypatch.setattr(todo_routes, "today_local", lambda: TODAY)
    monkeypatch.setattr(parent_todo.ai, "status", lambda: {"opening_confirmed": True, "rate_available": True})
    with closing(db.webapp_conn()) as c, c:
        for account in (1, 2):
            c.execute("INSERT INTO learning_profiles(account_id,school_year,grade,ai_enabled,active,created_at) "
                      "VALUES(?,?,?,?,?,?)", (account, "2026/2027", 6, 1, 1, "now"))
    data = client.get("/api/parent/todo").json()
    assert data["total"] == 0 and all(not k["items"] for k in data["kids"])
    # Ein Link zeigt ins Leere: blockierend ganz oben.
    with closing(db.webapp_conn()) as c, c:
        c.execute("INSERT INTO user_account_links VALUES(1,99,1)")
    data = client.get("/api/parent/todo").json()
    assert [b["kind"] for b in data["blocking"]] == ["stale_links"] and data["blocking"][0]["level"] == "block"
    assert data["total"] == 1


def test_todo_only_for_parents_in_their_own_view(env, monkeypatch):
    state = {"user": PARENT}
    client = _app(state)
    _fake_exams(monkeypatch)
    for mode in ("child", "mirror"):
        assert client.get("/api/parent/todo", headers={"x-view-mode": mode}).status_code == 403
    state["user"] = CHILD
    assert client.get("/api/parent/todo").status_code == 403


def test_daily_budget_is_set_by_parents_only(env):
    state = {"user": PARENT}
    client = _app(state)
    body = {"default_daily_budget_minutes": 45}
    assert client.patch("/api/accounts/1/settings", json=body, headers={"x-view-mode": "child"}).status_code == 403
    assert client.patch("/api/accounts/1/settings", json=body, headers={"x-view-mode": "mirror"}).status_code == 403
    state["user"] = CHILD
    assert client.patch("/api/accounts/1/settings", json=body).status_code == 403
    state["user"] = PARENT
    assert client.patch("/api/accounts/1/settings", json=body).status_code == 200
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT default_daily_budget_minutes FROM account_settings WHERE account_id=1").fetchone()[0] == 45


def test_my_changes_for_every_parent_but_only_their_own(env):
    other = CurrentUser(4, "test-4", "Test", "parent", False, "pin")
    state = {"user": other}
    client = _app(state)
    with closing(db.webapp_conn()) as c, c:
        mine = audit.log(c, user_id=4, account_id=1, op_type="insert", target_kind="task", target_id=1,
                         label="Eigene Aufgabe", after={"id": 1})
        theirs = audit.log(c, user_id=1, account_id=1, op_type="insert", target_kind="task", target_id=2,
                           label="Fremde Aufgabe", after={"id": 2})
    entries = client.get("/api/my-changes").json()["entries"]
    assert [e["label"] for e in entries] == ["Eigene Aufgabe"]
    assert client.post(f"/api/my-changes/{theirs}/revert").status_code == 404
    assert client.post(f"/api/my-changes/{mine}/revert").json() == {"ok": True}


def test_usage_ping_counts_child_mode_as_child(env, monkeypatch):
    state = {"user": PARENT}
    client = _app(state)
    seen = []
    monkeypatch.setattr(usage_routes.usage_report, "record_ping", lambda *a: seen.append(a[1]))
    monkeypatch.setattr(usage_routes.usage_report, "purge", lambda: None)
    body = {"account_id": 1, "view": "today", "seconds": 30}
    assert client.post("/api/usage/ping", json=body).status_code == 204
    assert client.post("/api/usage/ping", json=body, headers={"x-view-mode": "child"}).status_code == 204
    assert seen == ["parent", "child"]


def test_parent_tools_hidden_when_child_uses_the_device(env):
    state = {"user": PARENT}
    client = _app(state)
    assert client.get("/api/accounts/1/materials").json()["can_manage"] is True
    for mode in ("child", "mirror"):
        assert client.get("/api/accounts/1/materials", headers={"x-view-mode": mode}).json()["can_manage"] is False
    admin = client.get("/api/accounts/1/learning/mentor/admin")
    assert admin.status_code == 200 and admin.json()["enabled"] is True and admin.json()["profile"] is None
    assert "budget" in admin.json()
    assert client.get("/api/accounts/1/learning/mentor/admin", headers={"x-view-mode": "child"}).status_code == 403
    # Erinnerungen: Eltern stellen ein, das Kind am Elterngerät liest nur.
    assert client.get("/api/accounts/1/reminders").json()["can_manage"] is True
    assert client.get("/api/accounts/1/reminders", headers={"x-view-mode": "child"}).json()["can_manage"] is False
    assert client.get("/api/accounts/1/reminders", headers={"x-view-mode": "mirror"}).json()["can_manage"] is False
    body = {"enabled": True, "remind_at": "18:00"}
    assert client.put("/api/accounts/1/reminders", json=body, headers={"x-view-mode": "child"}).status_code == 403
    assert client.put("/api/accounts/1/reminders", json=body).status_code == 200
