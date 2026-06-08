"""PIN authentication for direct (non-Ingress) access.

A user with a PIN can log in over the add-on's direct port without going
through Home Assistant's Ingress proxy. This is what makes an installable
PWA on the home screen possible: when the device hits the add-on URL
directly, our HTML is the top frame and iOS Safari honours its manifest.

Security model
- 4–8 digit PIN per user, hashed with pbkdf2_hmac/sha256 + per-user salt
  (100 000 iterations — fine for stdlib, no extra dep, and brute-force is
  bounded by the lockout below)
- Wrong PIN: increment a counter. 5 failures lock the account for 5
  minutes; counter resets on a correct PIN.
- Successful login: 32 bytes of os.urandom → base64url token, stored in
  `sessions`, sent back as an HttpOnly `sc_session` cookie with 30-day
  expiry. Each request touches `last_seen_at` so we can purge stale rows.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone

SESSION_TTL_DAYS = 30
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 5
PBKDF2_ITERS = 100_000
SESSION_COOKIE = "sc_session"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(pin: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERS
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def set_pin(conn: sqlite3.Connection, user_id: int, pin: str) -> None:
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 8):
        raise ValueError("PIN muss 4–8 Ziffern haben")
    salt = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
    conn.execute(
        "UPDATE users SET pin_hash = ?, pin_salt = ?, "
        "pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?",
        (_hash(pin, salt), salt, user_id),
    )


def clear_pin(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET pin_hash = NULL, pin_salt = NULL, "
        "pin_failed_attempts = 0, pin_locked_until = NULL WHERE id = ?",
        (user_id,),
    )
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def has_pin(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT pin_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return bool(row and row["pin_hash"])


class PinError(Exception):
    def __init__(self, message: str, *, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


def verify_pin(conn: sqlite3.Connection, user_id: int, pin: str) -> bool:
    row = conn.execute(
        "SELECT pin_hash, pin_salt, pin_failed_attempts, pin_locked_until "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or not row["pin_hash"]:
        raise PinError("Kein PIN für diesen Nutzer gesetzt", status=400)

    if row["pin_locked_until"]:
        locked_until = datetime.fromisoformat(row["pin_locked_until"])
        if locked_until > _utc_now():
            remaining = int((locked_until - _utc_now()).total_seconds() // 60) + 1
            raise PinError(
                f"Zu viele Fehlversuche — bitte {remaining} Min warten",
                status=429,
            )

    if _hash(pin, row["pin_salt"]) == row["pin_hash"]:
        conn.execute(
            "UPDATE users SET pin_failed_attempts = 0, pin_locked_until = NULL "
            "WHERE id = ?",
            (user_id,),
        )
        return True

    attempts = (row["pin_failed_attempts"] or 0) + 1
    locked_until: str | None = None
    if attempts >= LOCKOUT_THRESHOLD:
        locked_until = (_utc_now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        attempts = 0
    conn.execute(
        "UPDATE users SET pin_failed_attempts = ?, pin_locked_until = ? WHERE id = ?",
        (attempts, locked_until, user_id),
    )
    return False


def create_session(conn: sqlite3.Connection, user_id: int) -> tuple[str, datetime]:
    token = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
    now = _utc_now()
    expires = now + timedelta(days=SESSION_TTL_DAYS)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token, user_id, now.isoformat(), expires.isoformat(), now.isoformat()),
    )
    return token, expires


def lookup_session(conn: sqlite3.Connection, token: str) -> int | None:
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < _utc_now():
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return None
    conn.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE token = ?",
        (_utc_now().isoformat(), token),
    )
    return row["user_id"]


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def cleanup_expired(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "DELETE FROM sessions WHERE expires_at < ?", (_utc_now().isoformat(),)
    )
    return cur.rowcount
