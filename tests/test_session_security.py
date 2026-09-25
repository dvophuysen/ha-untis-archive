"""Anmeldung: gehashte Sitzungen, PIN-Wechsel, verfallende Fehlversuche,
„zuletzt gesehen“ ohne Warten, Neuanlage ohne Doppel-Admin und das gleitende
Cookie nur für echte PIN-Anfragen."""
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import auth, db, pin_auth


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SETTINGS", SimpleNamespace(webapp_db_path=tmp_path / "webapp.db",
                                                        history_db_path=tmp_path / "h.db"))
    db.init_webapp_db()
    with db.webapp_conn() as c:
        for uid, name, role, admin in (("p1", "Elternteil", "parent", 1), ("k1", "Kind", "child", 0)):
            c.execute("INSERT INTO users (ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
                      "VALUES (?, ?, ?, ?, 'x', 'x')", (uid, name, role, admin))
        pin_auth.set_pin(c, 1, "1111")
        pin_auth.set_pin(c, 2, "2222")
    return tmp_path


def _sessions():
    with db.webapp_conn() as c:
        return [r[0] for r in c.execute("SELECT token FROM sessions ORDER BY created_at")]


def test_only_the_hash_of_a_session_is_stored(env):
    with db.webapp_conn() as c:
        token, _ = pin_auth.create_session(c, 2)
        assert pin_auth.lookup_session(c, token) == 2
        stored = _sessions()
        assert stored == [pin_auth.token_hash(token)] and token not in stored
        # Der Hash aus einer Sicherung ist selbst keine Anmeldung.
        assert pin_auth.lookup_session(c, stored[0]) is None


def test_existing_sessions_stay_valid_across_the_migration(env):
    raw = "A" * 43
    with db.webapp_conn() as c:
        now = datetime.now(timezone.utc)
        c.execute("INSERT INTO sessions (token, user_id, created_at, expires_at, last_seen_at) VALUES (?,2,?,?,?)",
                  (raw, now.isoformat(), (now + timedelta(days=30)).isoformat(), now.isoformat()))
        c.execute("DELETE FROM schema_meta WHERE key='migration:opt_core_001_session_token_hash'")
    db.init_webapp_db()
    assert _sessions() == [pin_auth.token_hash(raw)]
    with db.webapp_conn() as c:
        assert pin_auth.lookup_session(c, raw) == 2


def test_an_unmigrated_session_from_a_restored_backup_still_works_and_is_upgraded(env):
    raw = "B" * 43
    with db.webapp_conn() as c:
        now = datetime.now(timezone.utc)
        c.execute("INSERT INTO sessions (token, user_id, created_at, expires_at, last_seen_at) VALUES (?,2,?,?,?)",
                  (raw, now.isoformat(), (now + timedelta(days=30)).isoformat(), now.isoformat()))
        assert pin_auth.lookup_session(c, raw) == 2
    assert _sessions() == [pin_auth.token_hash(raw)]


def test_setting_a_pin_ends_other_sessions_but_keeps_the_own_one(env):
    with db.webapp_conn() as c:
        kid_phone, _ = pin_auth.create_session(c, 2)
        own, _ = pin_auth.create_session(c, 1)
        other, _ = pin_auth.create_session(c, 1)
        pin_auth.set_pin(c, 2, "3333")
        assert pin_auth.lookup_session(c, kid_phone) is None
        pin_auth.set_pin(c, 1, "4444", keep_token=own)
        assert pin_auth.lookup_session(c, own) == 1
        assert pin_auth.lookup_session(c, other) is None


def test_admin_changing_the_own_pin_stays_logged_in(env):
    from backend.routers import auth_router
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"user_id": 1, "pin": "1111"})
    assert r.status_code == 200
    with db.webapp_conn() as c:
        kid, _ = pin_auth.create_session(c, 2)
    assert client.put("/api/users/1/pin", json={"pin": "5555"}).status_code == 200
    assert client.get("/api/users/1/pin-status").status_code == 200, "eigenes Gerät bleibt angemeldet"
    assert client.put("/api/users/2/pin", json={"pin": "6666"}).status_code == 200
    with db.webapp_conn() as c:
        assert pin_auth.lookup_session(c, kid) is None


def _try(pin):
    with db.webapp_conn() as c:
        try:
            return pin_auth.verify_pin(c, 2, pin)
        except pin_auth.PinError as exc:
            return exc.status


def _age_failures(hours):
    with db.webapp_conn() as c:
        c.execute("UPDATE users SET pin_locked_until=NULL, pin_failed_at=? WHERE id=2",
                  ((datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(),))


def test_failures_are_forgotten_after_a_day_without_one(env):
    for _ in range(15):
        _try("0000")
        _age_failures(0)  # nur die Sperre aufheben, Zeit bleibt jetzt
    with db.webapp_conn() as c:
        assert c.execute("SELECT pin_failed_attempts FROM users WHERE id=2").fetchone()[0] == 15
    _age_failures(25)
    # Nach 24 Stunden Ruhe zählt der nächste Fehler wieder als erster: fünf
    # Fehler sperren nur fünf Minuten, nicht eine Stunde.
    for _ in range(5):
        assert _try("0000") is False
    with db.webapp_conn() as c:
        locked = datetime.fromisoformat(c.execute("SELECT pin_locked_until FROM users WHERE id=2").fetchone()[0])
    assert (locked - datetime.now(timezone.utc)).total_seconds() <= 5 * 60


def test_a_parent_reset_lifts_the_lock(env):
    for _ in range(5):
        _try("0000")
    assert _try("2222") == 429
    with db.webapp_conn() as c:
        pin_auth.set_pin(c, 2, "2222")
    assert _try("2222") is True


def _request(cookies=None, headers=None, host="10.0.0.5"):
    return SimpleNamespace(cookies=cookies or {}, headers=headers or {}, client=SimpleNamespace(host=host),
                           state=SimpleNamespace())


def test_last_seen_is_written_rarely_and_a_locked_database_does_not_fail_the_request(env, monkeypatch):
    with db.webapp_conn() as c:
        token, _ = pin_auth.create_session(c, 2)
        c.execute("UPDATE users SET last_seen_at=? WHERE id=2", (datetime.now(timezone.utc).isoformat(),))
        fresh = c.execute("SELECT last_seen_at FROM users WHERE id=2").fetchone()[0]
    req = _request({pin_auth.SESSION_COOKIE: token})
    assert auth.get_current_user(req).id == 2
    assert req.state.auth_source == "pin" and req.state.pin_token == token
    with db.webapp_conn() as c:
        assert c.execute("SELECT last_seen_at FROM users WHERE id=2").fetchone()[0] == fresh
        c.execute("UPDATE users SET last_seen_at='2000-01-01T00:00:00+00:00' WHERE id=2")
    blocker = sqlite3.connect(db.SETTINGS.webapp_db_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        start = datetime.now()
        assert auth.get_current_user(_request({pin_auth.SESSION_COOKIE: token})).id == 2
        assert (datetime.now() - start).total_seconds() < 5
        # Auch über Ingress scheitert die Anfrage nicht am Schreiben.
        monkeypatch.setattr(auth, "INGRESS_PEERS", frozenset({"172.30.32.2"}))
        ingress = _request(headers={"x-remote-user-id": "p1", "x-remote-user-name": "Elternteil"}, host="172.30.32.2")
        assert auth.get_current_user(ingress).id == 1
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    with db.webapp_conn() as c:
        assert c.execute("PRAGMA busy_timeout").fetchone()[0] == int(db.BUSY_TIMEOUT * 1000)
        c.execute("UPDATE users SET last_seen_at='2000-01-01T00:00:00+00:00' WHERE id=2")
    auth.get_current_user(_request({pin_auth.SESSION_COOKIE: token}))
    with db.webapp_conn() as c:
        assert c.execute("SELECT last_seen_at FROM users WHERE id=2").fetchone()[0] > "2020"


def test_parallel_first_requests_create_one_user_and_one_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SETTINGS", SimpleNamespace(webapp_db_path=tmp_path / "webapp.db",
                                                        history_db_path=tmp_path / "h.db"))
    db.init_webapp_db()
    monkeypatch.setattr(auth, "INGRESS_PEERS", frozenset({"172.30.32.2"}))
    errors, users = [], []

    def hit(uid):
        try:
            users.append(auth.get_current_user(_request(headers={"x-remote-user-id": uid}, host="172.30.32.2")))
        except Exception as exc:  # pragma: no cover - Fehlerfall
            errors.append(exc)

    threads = [threading.Thread(target=hit, args=(f"ha-{i % 2}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    with db.webapp_conn() as c:
        rows = c.execute("SELECT ha_user_id, is_admin FROM users ORDER BY id").fetchall()
    assert len(rows) == 2 and sum(r["is_admin"] for r in rows) == 1


# ---- gleitendes Cookie ------------------------------------------------------

def _app():
    """Die echte Middleware aus main.py an einer kleinen App."""
    from backend import main
    from backend.routers import kiosk
    app = FastAPI()
    app.middleware("http")(main.slide_pin_cookie)
    app.include_router(kiosk.router)

    @app.get("/api/ping")
    def ping(user=Depends(auth.get_current_user)):
        return {"id": user.id}

    @app.get("/api/public")
    def public():
        return {"ok": True}

    return app


def test_the_cookie_slides_for_pin_requests_only(env):
    client = TestClient(_app())
    with db.webapp_conn() as c:
        token, _ = pin_auth.create_session(c, 2)
    client.cookies.set(pin_auth.SESSION_COOKIE, token)
    r = client.get("/api/ping")
    assert r.status_code == 200 and f"{pin_auth.SESSION_COOKIE}={token}" in r.headers.get("set-cookie", "")
    # Ohne Anmeldung (oder mit ungültigem Cookie) wird nichts verlängert.
    assert "set-cookie" not in client.get("/api/public").headers
    client.cookies.clear()
    client.cookies.set(pin_auth.SESSION_COOKIE, "ungueltig")
    r = client.get("/api/ping")
    assert r.status_code == 401 and "set-cookie" not in r.headers


def test_kiosk_login_keeps_its_new_cookie_despite_a_stale_one(env):
    client = TestClient(_app(), follow_redirects=False)
    client.cookies.set(pin_auth.SESSION_COOKIE, "abgelaufen-und-alt")
    r = client.post("/kiosk/login", data={"user_id": "2", "pin": "2222"})
    assert r.status_code == 303
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 1 and "abgelaufen-und-alt" not in cookies[0]
    new = cookies[0].split(";")[0].split("=", 1)[1]
    with db.webapp_conn() as c:
        assert pin_auth.lookup_session(c, new) == 2
    # Die Kiosk-Seite selbst verlängert die Sitzung weiter.
    client.cookies.clear()
    client.cookies.set(pin_auth.SESSION_COOKIE, new)
    page = client.get("/kiosk")
    assert f"{pin_auth.SESSION_COOKIE}={new}" in page.headers.get("set-cookie", "")
