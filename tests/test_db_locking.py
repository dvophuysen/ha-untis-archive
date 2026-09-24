"""Ein anderer Schreiber darf keine gewöhnliche Anfrage scheitern lassen.

Im Betrieb schlugen während einer Sicherung fünfzehn Anfragen mit „database
is locked" fehl: Die Datei lief ohne WAL, jeder Leser hielt Schreiber an, und
jede Anfrage schreibt beim Anmelden „zuletzt gesehen"."""
import sqlite3
from types import SimpleNamespace

import pytest

from backend import auth, db


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db, "SETTINGS",
        SimpleNamespace(webapp_db_path=tmp_path / "webapp.db", history_db_path=tmp_path / "h.db"),
    )
    monkeypatch.setattr(db, "BUSY_TIMEOUT", 0.2)
    db.init_webapp_db()
    with db.webapp_conn() as c:
        c.execute(
            "INSERT INTO users (ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
            "VALUES ('u1', 'Elternteil', 'admin', 1, 'x', 'x')"
        )
    return tmp_path


def test_database_runs_in_wal_mode(env):
    with db.webapp_conn() as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_login_survives_a_writer_holding_the_file(env):
    request = SimpleNamespace(headers={"x-remote-user-id": "u1", "x-remote-user-name": "Elternteil"}, cookies={},
                              client=SimpleNamespace(host="172.30.32.2"))
    blocker = sqlite3.connect(env / "webapp.db", isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute("UPDATE users SET display_name = display_name")
    try:
        user = auth.get_current_user(request)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert user.display_name == "Elternteil" and user.is_admin


def test_ingress_headers_count_only_from_the_ingress_proxy(env):
    """Bis 1.13.11 war über den Direktport jeder mit einer bekannten
    HA-Benutzer-ID ohne PIN angemeldet, auch als Admin."""
    import pytest
    from fastapi import HTTPException
    forged = SimpleNamespace(headers={"x-remote-user-id": "u1"}, cookies={},
                             client=SimpleNamespace(host="172.30.33.5"))
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(forged)
    assert exc.value.status_code == 401
    # Eine unbekannte ID legt von außen auch keinen neuen Nutzer mehr an.
    stranger = SimpleNamespace(headers={"x-remote-user-id": "neu"}, cookies={},
                               client=SimpleNamespace(host="192.168.1.20"))
    with pytest.raises(HTTPException):
        auth.get_current_user(stranger)
    with db.webapp_conn() as c:
        assert c.execute("SELECT COUNT(*) FROM users WHERE ha_user_id='neu'").fetchone()[0] == 0
    # Ohne Gegenstelle (etwa ein Aufruf ohne Verbindung) gilt die Kopfzeile nicht.
    with pytest.raises(HTTPException):
        auth.get_current_user(SimpleNamespace(headers={"x-remote-user-id": "u1"}, cookies={}))
