"""Die PIN-Sperre muss auch gleichzeitige Versuche zählen und bei
fortgesetztem Raten länger werden. Bis 1.13.12 lösten 40 parallele
Fehlversuche keine Sperre aus, und nach jeder Sperre begann die Zählung
wieder bei null."""
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend import db, pin_auth


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db, "SETTINGS",
        SimpleNamespace(webapp_db_path=tmp_path / "webapp.db", history_db_path=tmp_path / "h.db"),
    )
    db.init_webapp_db()
    with db.webapp_conn() as c:
        c.execute(
            "INSERT INTO users (ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
            "VALUES ('k1', 'Kind', 'child', 0, 'x', 'x')"
        )
        pin_auth.set_pin(c, 1, "4711")
    return tmp_path


def _try(pin):
    c = db.webapp_conn()
    try:
        return pin_auth.verify_pin(c, 1, pin)
    except pin_auth.PinError as exc:
        return exc.status
    finally:
        c.close()


def _state():
    with db.webapp_conn() as c:
        return c.execute("SELECT pin_failed_attempts, pin_locked_until FROM users WHERE id=1").fetchone()


def _unlock():
    with db.webapp_conn() as c:
        c.execute("UPDATE users SET pin_locked_until=? WHERE id=1",
                  ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))


def test_parallel_attempts_cannot_slip_past_the_lock(env):
    results = []
    threads = [threading.Thread(target=lambda: results.append(_try("0000"))) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Genau fünf Versuche werden geprüft, alle weiteren prallen an der Sperre ab.
    assert results.count(False) == 5 and results.count(429) == 15
    assert _try("4711") == 429, "auch die richtige PIN wartet die Sperre ab"


def test_the_lock_grows_while_guessing_goes_on_and_a_correct_pin_resets(env):
    expected = [5, 15, 60, 24 * 60, 24 * 60]
    for minutes in expected:
        for _ in range(5):
            assert _try("0000") is False
        locked = datetime.fromisoformat(_state()["pin_locked_until"])
        left = (locked - datetime.now(timezone.utc)).total_seconds() / 60
        assert minutes - 1 < left <= minutes
        assert _try("0000") == 429
        _unlock()
    assert _try("4711") is True
    row = _state()
    assert row["pin_failed_attempts"] == 0 and row["pin_locked_until"] is None


def test_a_single_typo_costs_nothing_and_a_new_pin_unlocks(env):
    assert _try("4712") is False
    assert _try("4711") is True
    for _ in range(5):
        _try("0000")
    assert _try("4711") == 429
    with db.webapp_conn() as c:
        pin_auth.set_pin(c, 1, "1234")
    assert _try("1234") is True
