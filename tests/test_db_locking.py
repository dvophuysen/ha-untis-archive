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
            "VALUES ('u1', 'Dennis', 'admin', 1, 'x', 'x')"
        )
    return tmp_path


def test_database_runs_in_wal_mode(env):
    with db.webapp_conn() as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_login_survives_a_writer_holding_the_file(env):
    request = SimpleNamespace(headers={"x-remote-user-id": "u1", "x-remote-user-name": "Dennis"}, cookies={})
    blocker = sqlite3.connect(env / "webapp.db", isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute("UPDATE users SET display_name = display_name")
    try:
        user = auth.get_current_user(request)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()
    assert user.display_name == "Dennis" and user.is_admin
