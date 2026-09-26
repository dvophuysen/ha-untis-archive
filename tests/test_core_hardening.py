"""Härtung rund um Anmeldung, Datenpflege und Start: Gesundheitsseite,
Mitteilungs-Token, Suche, Rückgängig, Familienkarte, Kiosk, history.db-Prüfung,
Wiederherstellung und Hintergrundaufgaben."""
import asyncio
import logging
import os
import sqlite3
import subprocess
import sys
import textwrap
import zipfile
from contextlib import closing
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import audit, backup, db, history_schema, learning, pin_auth, queries, view_mode
from backend.auth import CurrentUser, get_current_user

ROOT = Path(__file__).resolve().parents[1] / "schul_cockpit"
PARENT = CurrentUser(1, "p", "Elternteil", "parent", True, "pin")
CHILD = CurrentUser(2, "k", "Kind", "child", False, "pin")


@pytest.fixture
def env(tmp_path, monkeypatch):
    history = tmp_path / "history.db"
    with sqlite3.connect(history) as c:
        c.executescript("""
            CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT, entry_id TEXT);
            INSERT INTO accounts VALUES (1, 'Kind A', 'entry-a');
            CREATE TABLE lessons(id INTEGER PRIMARY KEY, account_id INTEGER, date TEXT, start_time INTEGER,
              end_time INTEGER, subject_name TEXT, teacher_name TEXT, room TEXT, lstext TEXT, subst_text TEXT,
              info TEXT, period_info_json TEXT, subject_untis_id INTEGER, was_absent INTEGER, code TEXT);
        """)
    settings = SimpleNamespace(webapp_db_path=tmp_path / "webapp.db", history_db_path=history)
    monkeypatch.setattr(db, "SETTINGS", settings)
    # backup.py liest config.SETTINGS: ohne das landeten Testdateien in /data.
    monkeypatch.setattr(backup, "SETTINGS", settings)
    db.init_webapp_db()
    with closing(db.webapp_conn()) as c:
        for uid, ha, name, role, admin in ((1, "p", "Elternteil", "parent", 1), (2, "k", "Kind", "child", 0)):
            c.execute("INSERT INTO users (id, ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
                      "VALUES (?, ?, ?, ?, ?, 'x', 'x')", (uid, ha, name, role, admin))
        c.execute("INSERT INTO user_account_links VALUES (1, 1, 1), (2, 1, 1)")
    return tmp_path


def _client(*routers, user=PARENT, prefix="/api"):
    app = FastAPI()
    app.middleware("http")(view_mode.middleware)
    for r in routers:
        app.include_router(r, prefix=prefix)
    state = SimpleNamespace(user=user)
    app.dependency_overrides[get_current_user] = lambda: state.user
    client = TestClient(app)
    client.state = state
    return client


# ---- /api/health -------------------------------------------------------------

def test_health_shows_names_and_paths_only_to_an_admin(env, monkeypatch):
    from backend.routers import health
    client = _client(health.router)
    public = client.get("/api/health").json()
    assert public == {"ok": True, "history_db_accessible": True}
    monkeypatch.setattr(health, "get_current_user", lambda request: PARENT)
    admin = client.get("/api/health").json()
    assert admin["accounts"] == [{"id": 1, "name": "Kind A"}] and "webapp_db" in admin
    monkeypatch.setattr(health, "get_current_user", lambda request: CHILD)
    assert "accounts" not in client.get("/api/health").json()


# ---- Mitteilungs-Token -------------------------------------------------------

def test_notify_token_via_header_or_query_and_odd_tokens_are_a_plain_401(env):
    from backend.routers import notify
    with db.webapp_conn() as c:
        c.execute("INSERT INTO account_settings(account_id, notify_token, created_at, updated_at) "
                  "VALUES (9, 'geheim-9', 'x', 'x')")
    client = _client(notify.router)
    assert client.get("/api/notify/9/summary").status_code == 401
    assert client.get("/api/notify/9/summary", params={"token": "falsch"}).status_code == 401
    assert client.get("/api/notify/9/summary", params={"token": "täuschung"}).status_code == 401
    # Richtiges Token: weiter bis zur Kontoprüfung (Konto 9 gibt es in history.db nicht).
    assert client.get("/api/notify/9/summary", params={"token": "geheim-9"}).status_code == 404
    assert client.get("/api/notify/9/summary", headers={"X-Notify-Token": "geheim-9"}).status_code == 404
    assert notify.token_matches("geheim", "geheim") and not notify.token_matches("geheim", "gehäim")


def test_tokens_are_masked_in_the_access_log():
    from backend.main import MaskQueryTokens
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ("1.2.3.4:5", "GET", "/api/notify/1/summary?token=abc123&x=1", "1.1", 200), None)
    MaskQueryTokens().filter(record)
    line = record.getMessage()
    assert "abc123" not in line and "token=***&x=1" in line and "/api/notify/1/summary" in line


def test_upcoming_exams_count_from_the_german_day(env, monkeypatch):
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        for i, day in enumerate(("2026-09-25", "2026-09-26", "2026-10-10", "2026-10-11")):
            c.execute("INSERT INTO lessons(id, account_id, date, start_time, subject_name, period_info_json) "
                      "VALUES (?, 1, ?, 800, 'Mathe', '{\"exam\": {\"name\": \"Arbeit\"}}')", (i + 1, day))
    monkeypatch.setattr(learning, "today_local", lambda: date(2026, 9, 26))
    with db.history_conn() as h:
        got = [e["date"] for e in queries.upcoming_exams(h, 1, days_ahead=14)]
    assert got == ["2026-09-26", "2026-10-10"]


# ---- Suche -------------------------------------------------------------------

def test_search_folds_umlauts_and_treats_wildcards_literally(env):
    from backend.routers import search
    with sqlite3.connect(db.SETTINGS.history_db_path) as c:
        c.execute("INSERT INTO lessons(id, account_id, date, start_time, subject_name, lstext) "
                  "VALUES (1, 1, '2026-09-20', 800, 'Deutsch', 'ÜBUNG zur Straße')")
        c.execute("INSERT INTO lessons(id, account_id, date, start_time, subject_name, lstext) "
                  "VALUES (2, 1, '2026-09-21', 800, 'Mathe', 'Brüche')")
    with db.webapp_conn() as c:
        c.execute("INSERT INTO lesson_checkins(account_id, lesson_id, user_id, rating, note, created_at, updated_at) "
                  "VALUES (1, 2, 2, 3, '100% verstanden', 'x', 'x')")
    client = _client(search.router)

    def hits(q):
        r = client.get("/api/accounts/1/search", params={"q": q}).json()
        return [h["lesson_id"] for g in r["groups"] for h in g["hits"]], [n["lesson_id"] for n in r["personal_note_hits"]]

    assert hits("übung") == ([1], [])
    assert hits("STRASSE") == ([1], [])
    assert hits("%%") == ([], [])
    assert hits("__") == ([], [])
    assert hits("0% v") == ([], [2])


# ---- Rückgängig --------------------------------------------------------------

def test_revert_refuses_to_overwrite_a_newer_change(env):
    from backend.routers import audit as audit_routes, tasks as task_routes
    client = _client(task_routes.router, audit_routes.router)
    tid = client.post("/api/accounts/1/tasks", json={"title": "Blatt"}).json()["id"]
    assert client.patch(f"/api/tasks/{tid}", json={"notes": "vom Elternteil"}).status_code == 200
    client.state.user = CHILD
    assert client.patch(f"/api/tasks/{tid}", json={"notes": "vom Kind"}).status_code == 200
    client.state.user = PARENT
    mine = [e for e in client.get("/api/my-changes").json()["entries"] if e["op_type"] == "update"]
    r = client.post(f"/api/my-changes/{mine[0]['id']}/revert")
    assert r.status_code == 409 and "neuere Änderung" in r.json()["detail"]
    with db.webapp_conn() as c:
        assert c.execute("SELECT notes FROM tasks WHERE id=?", (tid,)).fetchone()[0] == "vom Kind"
        assert c.execute("SELECT reverted_at FROM audit_log WHERE id=?", (mine[0]["id"],)).fetchone()[0] is None
    # Das Anlegen lässt sich auch nicht mehr zurücknehmen: danach wurde geändert.
    created = [e for e in client.get("/api/my-changes").json()["entries"] if e["op_type"] == "insert"][0]
    assert client.post(f"/api/my-changes/{created['id']}/revert").status_code == 409


def test_revert_still_works_when_nothing_changed_since(env):
    from backend.routers import audit as audit_routes, tasks as task_routes
    client = _client(task_routes.router, audit_routes.router)
    tid = client.post("/api/accounts/1/tasks", json={"title": "Blatt"}).json()["id"]
    client.patch(f"/api/tasks/{tid}", json={"notes": "neu"})
    entries = client.get("/api/my-changes").json()["entries"]
    upd = next(e for e in entries if e["op_type"] == "update")
    assert client.post(f"/api/my-changes/{upd['id']}/revert").json() == {"ok": True}
    assert client.post(f"/api/my-changes/{upd['id']}/revert").json()["already_reverted"] is True
    with db.webapp_conn() as c:
        assert c.execute("SELECT notes FROM tasks WHERE id=?", (tid,)).fetchone()[0] is None


def test_leaving_test_mode_skips_conflicts_and_reverts_the_rest(env):
    from backend.routers import audit as audit_routes, tasks as task_routes
    client = _client(task_routes.router, audit_routes.router)
    with db.webapp_conn() as c:
        c.execute("UPDATE users SET demo_mode=1 WHERE id=1")
    a = client.post("/api/accounts/1/tasks", json={"title": "Test A"}).json()["id"]
    b = client.post("/api/accounts/1/tasks", json={"title": "Test B"}).json()["id"]
    client.patch(f"/api/tasks/{a}", json={"notes": "Testmodus"})
    client.state.user = CHILD  # das Kind ändert B danach wirklich
    client.patch(f"/api/tasks/{b}", json={"notes": "echt"})
    client.state.user = PARENT
    r = client.post("/api/my-changes/revert-all-demo").json()
    assert r["reverted"] == 2 and r["skipped"] == 1
    with db.webapp_conn() as c:
        assert [row[0] for row in c.execute("SELECT id FROM tasks")] == [b]


# ---- Familienkarte und Kiosk -------------------------------------------------

def test_family_board_is_for_parents_only(env, monkeypatch):
    from backend.routers import dashboard

    async def board(account_id, name, today):
        return {"account_id": account_id, "name": name}

    monkeypatch.setattr(dashboard, "_dashboard_for_account", board)
    client = _client(dashboard.router)
    assert client.get("/api/dashboard").json()["kids"] == [{"account_id": 1, "name": "Kind A"}]
    assert client.get("/api/dashboard", headers={"x-view-mode": "test"}).status_code == 200
    assert client.get("/api/dashboard", headers={"x-view-mode": "child"}).status_code == 403
    assert client.get("/api/dashboard", headers={"x-view-mode": "mirror"}).status_code == 403
    client.state.user = CHILD
    assert client.get("/api/dashboard").status_code == 403


def test_the_kiosk_stays_open_to_children_without_parent_observations(env, monkeypatch):
    from backend.routers import kiosk

    async def board(account_id, name, today):
        return {"name": name, "exams": [{"date": "2026-10-01", "days_until": 5, "subject_short": "Ma",
                                         "priority": "red", "comprehension": {"hard": 2, "total": 3}}],
                "support": [{"subject_short": "Ma", "hard_count": 2, "total_count": 3}],
                "tasks": {"open_count": 0, "items": []}, "plan": {}}

    monkeypatch.setattr(kiosk, "_dashboard_for_account", board)
    app = FastAPI()
    app.include_router(kiosk.router)
    client = TestClient(app)
    with db.webapp_conn() as c:
        kid, _ = pin_auth.create_session(c, 2)
        parent, _ = pin_auth.create_session(c, 1)
    client.cookies.set(pin_auth.SESSION_COOKIE, kid)
    page = client.get("/kiosk")
    assert page.status_code == 200 and "Kind A" in page.text
    assert "<h3>Mitlernen" not in page.text and "· 2 schwer" not in page.text
    client.cookies.clear()
    client.cookies.set(pin_auth.SESSION_COOKIE, parent)
    page = client.get("/kiosk").text
    assert "<h3>Mitlernen" in page and "· 2 schwer" in page


# ---- history.db, Start und Hintergrund --------------------------------------

def test_an_unreadable_history_db_is_a_schema_mismatch_not_a_crash(tmp_path):
    bad = tmp_path / "history.db"
    bad.write_bytes(b"das ist keine Datenbank" * 100)
    with pytest.raises(history_schema.SchemaMismatch):
        history_schema.assert_compatible(str(bad))


def test_stopping_background_tasks_survives_a_task_that_fails(caplog):
    from backend import main

    async def run():
        async def boom():
            raise ValueError("kaputt")

        async def forever():
            await asyncio.sleep(3600)

        async def stubborn():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise RuntimeError("beim Beenden") from None

        tasks = [main._start("boom", boom()), main._start("stubborn", stubborn()), main._start("forever", forever())]
        await asyncio.sleep(0.05)
        await main._stop(tasks)
        return tasks

    with caplog.at_level(logging.ERROR, logger="schul_cockpit"):
        tasks = asyncio.run(run())
    assert all(t.done() for t in tasks)
    assert any("boom" in r.getMessage() for r in caplog.records)


def test_unknown_api_paths_answer_404_and_the_app_still_loads(tmp_path):
    front = tmp_path / "front"
    front.mkdir()
    (front / "index.html").write_text("<html>app</html>")
    data = tmp_path / "data"
    data.mkdir()
    script = textwrap.dedent("""
        from fastapi.testclient import TestClient
        from backend.db import init_webapp_db
        from backend.main import app
        init_webapp_db()
        c = TestClient(app)
        r = c.get("/api/gibt-es-nicht")
        assert r.status_code == 404 and r.json() == {"detail": "Not Found"}, r.text
        assert c.get("/api").status_code == 404
        assert "app" in c.get("/irgendeine/seite").text
        h = c.get("/api/health")
        assert h.status_code == 200 and "accounts" not in h.json() and "webapp_db" not in h.json(), h.text
        print("ok")
    """)
    env = {**os.environ, "WEBAPP_FRONTEND_DIR": str(front), "WEBAPP_DATA_DIR": str(data),
           "WEBAPP_HISTORY_DB": str(tmp_path / "history.db")}
    out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr[-2000:]


# ---- Wiederherstellung -------------------------------------------------------

def _backup_zip(tmp_path, marker: str) -> Path:
    src = tmp_path / f"src-{marker}.db"
    with closing(db.webapp_conn()) as live, closing(sqlite3.connect(src)) as dst:
        live.backup(dst)
    with closing(sqlite3.connect(src, isolation_level=None)) as c:
        c.execute("UPDATE users SET display_name=? WHERE id=1", (marker,))
    z = tmp_path / f"{marker}.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(src, "webapp.db")
    return z


def test_restore_is_staged_and_swapped_at_the_next_start(env):
    z = _backup_zip(env, "aus-dem-backup")
    info = backup.stage_restore(z)
    assert backup.pending_path().exists() and info["history_db_in_archive"] is False
    with closing(db.webapp_conn()) as c:  # bis zum Neustart läuft der bisherige Stand
        assert c.execute("SELECT display_name FROM users WHERE id=1").fetchone()[0] == "Elternteil"
        c.execute("UPDATE users SET display_name='zuletzt' WHERE id=2")
    bak = backup.apply_pending_restore()
    assert bak and not backup.pending_path().exists()
    db.init_webapp_db()
    with closing(db.webapp_conn()) as c:
        assert c.execute("SELECT display_name FROM users WHERE id=1").fetchone()[0] == "aus-dem-backup"
    with closing(sqlite3.connect(env / bak)) as c:  # die Kopie enthält auch die letzte Änderung
        assert c.execute("SELECT display_name FROM users WHERE id=2").fetchone()[0] == "zuletzt"
    assert backup.apply_pending_restore() is None


def test_a_bad_upload_is_rejected_and_leaves_no_files(env):
    junk = env / "junk.db"
    junk.write_bytes(b"x" * 4096)
    with pytest.raises(ValueError):
        backup.stage_restore(junk)
    assert not backup.pending_path().exists()
    assert not [p for p in env.iterdir() if ".restore-pending" in p.name]


def test_a_broken_pending_file_is_set_aside_and_the_live_db_stays(env):
    backup.pending_path().write_bytes(b"kaputt" * 1000)
    assert backup.apply_pending_restore() is None
    assert not backup.pending_path().exists()
    assert [p for p in env.iterdir() if ".rejected-" in p.name]
    with db.webapp_conn() as c:
        assert c.execute("SELECT display_name FROM users WHERE id=1").fetchone()[0] == "Elternteil"


def test_restore_endpoint_restarts_through_the_supervisor_when_it_can(env, monkeypatch):
    from backend.routers import backup as backup_routes
    calls = []

    async def restart():
        calls.append("restart")

    monkeypatch.setattr(backup_routes, "_restart_self", restart)
    client = _client(backup_routes.router)
    z = _backup_zip(env, "neu")
    monkeypatch.setattr(backup_routes, "get_supervisor", lambda: SimpleNamespace(available=False))
    r = client.post("/api/admin/backup/restore", files={"file": ("b.zip", z.read_bytes(), "application/zip")}).json()
    assert r["restart_required"] is True and r["restarting"] is False and calls == []
    monkeypatch.setattr(backup_routes, "get_supervisor", lambda: SimpleNamespace(available=True))
    with TestClient(client.app) as tc:  # eigene Schleife, damit die Aufgabe laufen kann
        tc.app.dependency_overrides[get_current_user] = lambda: PARENT
        r = tc.post("/api/admin/backup/restore", files={"file": ("b.zip", z.read_bytes(), "application/zip")}).json()
    assert r["restarting"] is True and r["restart_required"] is False
    assert backup.pending_path().exists()


def test_slow_requests_are_logged_without_query(monkeypatch, caplog):
    """Messen statt schätzen: Server-Timing je Antwort, langsame API-Aufrufe
    im Log, ohne Query (dort kann ein Token stehen)."""
    import logging
    from fastapi.testclient import TestClient
    from backend import main
    monkeypatch.setattr(main, "SLOW_MS", 0)
    with TestClient(main.app) as client, caplog.at_level(logging.INFO, logger="schul_cockpit"):
        r = client.get("/api/health?token=geheim")
    assert r.headers["server-timing"].startswith("app;dur=")
    lines = [m for m in caplog.messages if m.startswith("langsam:")]
    assert lines and "/api/health" in lines[-1] and "geheim" not in lines[-1]
