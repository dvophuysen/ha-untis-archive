"""PIN authentication for direct (non-Ingress) access.

A user with a PIN can log in over the add-on's direct port without going
through Home Assistant's Ingress proxy. This is what makes an installable
PWA on the home screen (and offline use) possible: when the device hits the
add-on URL directly, our HTML is the top frame and iOS Safari honours its
manifest + service worker.

Security model
- 4–8 digit PIN per user, hashed with pbkdf2_hmac/sha256 + per-user salt
  (200 000 iterations — stdlib only, no extra dependency).
- Every attempt is counted before the hash is computed, so parallel
  attempts cannot slip past the lock. Every 5th failure locks the account,
  for 5 min, 15 min, 1 h and then 24 h; a correct or newly set PIN resets.
  Nach 24 Stunden ohne Fehlversuch beginnt die Zählung wieder bei null.
- Successful login: 32 bytes of os.urandom → base64url token, returned as an
  HttpOnly `sc_session` cookie (SESSION_TTL_DAYS, gleitend verlängert).
  In `sessions` steht nur sha256(token): Eine Sicherung der Datenbank enthält
  damit keine übernehmbare Anmeldung.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timedelta, timezone

SESSION_TTL_DAYS = 365
LOCKOUT_THRESHOLD = 5
# Sperrdauer je Sperre in Minuten; ab der vierten bleibt es bei 24 Stunden.
LOCKOUT_STEPS_MINUTES = (5, 15, 60, 24 * 60)
# So lange ohne Fehlversuch, dann zählt die nächste falsche PIN wieder als erste.
FAILURE_MEMORY_HOURS = 24
PBKDF2_ITERS = 200_000
SESSION_COOKIE = "sc_session"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(pin: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERS
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def token_hash(token: str) -> str:
    """So steht ein Sitzungs-Token in der Datenbank (64 Hex-Zeichen)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _looks_raw(token: str) -> bool:
    """Rohe Tokens haben 43 Zeichen, gespeicherte Hashes 64. Ein Cookie mit
    Hash-Länge wird nie direkt verglichen, sonst wäre ein Hash aus einer
    Sicherung selbst eine Anmeldung."""
    return len(token) != 64


def set_pin(conn: sqlite3.Connection, user_id: int, pin: str, *, keep_token: str | None = None) -> None:
    """Setzt die PIN und hebt eine Sperre auf. Alle Anmeldungen des Nutzers
    enden, außer der mit ``keep_token``: Wer die eigene PIN ändert, bleibt auf
    diesem Gerät angemeldet."""
    if not pin or not pin.isdigit() or not (4 <= len(pin) <= 8):
        raise ValueError("PIN muss 4–8 Ziffern haben")
    salt = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
    keep = (token_hash(keep_token), keep_token) if keep_token else ("", "")
    own = not conn.in_transaction
    if own:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE users SET pin_hash = ?, pin_salt = ?, "
            "pin_failed_attempts = 0, pin_locked_until = NULL, pin_failed_at = NULL WHERE id = ?",
            (_hash(pin, salt), salt, user_id),
        )
        conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token NOT IN (?, ?)",
            (user_id, *keep),
        )
        if own:
            conn.execute("COMMIT")
    except BaseException:
        if own and conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def clear_pin(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET pin_hash = NULL, pin_salt = NULL, "
        "pin_failed_attempts = 0, pin_locked_until = NULL, pin_failed_at = NULL WHERE id = ?",
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


def lockout_minutes(failures: int) -> int:
    """Sperrdauer nach der n-ten Sperre: 5 min, 15 min, 1 h, danach 24 h."""
    steps = LOCKOUT_STEPS_MINUTES
    return steps[min(max(failures // LOCKOUT_THRESHOLD, 1), len(steps)) - 1]


def _older_than(stamp: str | None, now: datetime, age: timedelta) -> bool:
    """Ob ein Zeitstempel älter als ``age`` ist. Fehlt er (Zähler von vor
    dieser Spalte), gilt er als alt."""
    if not stamp:
        return True
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return now - when > age


def verify_pin(conn: sqlite3.Connection, user_id: int, pin: str) -> bool:
    """Prüft eine PIN. Der Versuch wird gezählt, bevor gerechnet wird.

    Bis 1.13.12 las die Prüfung den Zähler, rechnete 200 000 Runden und schrieb
    erst danach: Gleichzeitige Versuche sahen alle denselben Stand, und 40
    parallele Fehlversuche lösten keine Sperre aus. Jetzt setzt eine kurze
    Schreibtransaktion den Zähler vorab hoch und sperrt beim fünften Versuch
    sofort für alle weiteren. Der Zähler läuft über Sperren hinweg weiter, so
    wächst die Sperre bei fortgesetztem Raten (5 min, 15 min, 1 h, 24 h); eine
    richtige PIN oder eine neu gesetzte PIN setzt alles zurück. Liegt der
    letzte Fehlversuch mehr als FAILURE_MEMORY_HOURS zurück, beginnt die
    Zählung neu: Wer sich einmal oft vertippt hat, landet beim nächsten Mal
    nicht gleich in der 24-Stunden-Sperre."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT pin_hash, pin_salt, pin_failed_attempts, pin_locked_until, pin_failed_at "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row or not row["pin_hash"]:
            raise PinError("Kein PIN für diesen Nutzer gesetzt", status=400)

        now = _utc_now()
        if row["pin_locked_until"]:
            locked_until = datetime.fromisoformat(row["pin_locked_until"])
            if locked_until > now:
                remaining = int((locked_until - now).total_seconds() // 60) + 1
                raise PinError(
                    f"Zu viele Fehlversuche — bitte {remaining} Min warten",
                    status=429,
                )

        previous = row["pin_failed_attempts"] or 0
        if previous and _older_than(row["pin_failed_at"], now, timedelta(hours=FAILURE_MEMORY_HOURS)):
            previous = 0
        attempts = previous + 1
        locked: str | None = None
        if attempts % LOCKOUT_THRESHOLD == 0:
            locked = (now + timedelta(minutes=lockout_minutes(attempts))).isoformat()
        conn.execute(
            "UPDATE users SET pin_failed_attempts = ?, pin_locked_until = ?, pin_failed_at = ? WHERE id = ?",
            (attempts, locked, now.isoformat(), user_id),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise

    if hmac.compare_digest(_hash(pin, row["pin_salt"]), row["pin_hash"]):
        conn.execute(
            "UPDATE users SET pin_failed_attempts = 0, pin_locked_until = NULL, pin_failed_at = NULL "
            "WHERE id = ?",
            (user_id,),
        )
        return True
    return False


def create_session(conn: sqlite3.Connection, user_id: int) -> tuple[str, datetime]:
    token = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
    now = _utc_now()
    expires = now + timedelta(days=SESSION_TTL_DAYS)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token_hash(token), user_id, now.isoformat(), expires.isoformat(), now.isoformat()),
    )
    return token, expires


SEEN_EVERY = 5  # Minuten zwischen zwei Schreibzugriffen auf die Anmeldung


def _find_session(conn: sqlite3.Connection, token: str):
    """Die Zeile zum Cookie und ihr Schlüssel in der Tabelle. Übergangsweise
    auch eine noch ungehashte Zeile (etwa aus einer älteren, gerade
    zurückgespielten Sicherung); sie wird dabei auf den Hash umgestellt."""
    key = token_hash(token)
    row = conn.execute(
        "SELECT user_id, expires_at, last_seen_at FROM sessions WHERE token = ?", (key,)
    ).fetchone()
    if row is not None or not _looks_raw(token):
        return row, key
    row = conn.execute(
        "SELECT user_id, expires_at, last_seen_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None, key
    try:
        conn.execute("UPDATE sessions SET token = ? WHERE token = ?", (key, token))
    except sqlite3.Error:
        return row, token  # gesperrt: beim nächsten Aufruf
    return row, key


def lookup_session(conn: sqlite3.Connection, token: str) -> int | None:
    if not token:
        return None
    row, key = _find_session(conn, token)
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < _utc_now():
        try:
            conn.execute("DELETE FROM sessions WHERE token = ?", (key,))
        except sqlite3.OperationalError:
            pass  # beim nächsten Aufruf
        return None
    # Sliding expiration: every successful auth pushes the expiry forward
    # by another full TTL. As long as the kid opens the app at least once
    # within SESSION_TTL_DAYS, they stay logged in indefinitely.
    # Geschrieben wird höchstens alle SEEN_EVERY Minuten, und eine gesperrte
    # Datenbank lässt die Anmeldung trotzdem gelten: Parallele Aufrufe einer
    # Seite scheiterten sonst mit „database is locked“ (D200).
    now_dt = _utc_now()
    try:
        seen = datetime.fromisoformat(row["last_seen_at"]) if row["last_seen_at"] else None
    except ValueError:
        seen = None
    if seen is None or now_dt - seen >= timedelta(minutes=SEEN_EVERY):
        try:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token = ?",
                (now_dt.isoformat(), (now_dt + timedelta(days=SESSION_TTL_DAYS)).isoformat(), key),
            )
        except sqlite3.OperationalError:
            pass
    return row["user_id"]


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    raw = token if _looks_raw(token) else ""
    conn.execute("DELETE FROM sessions WHERE token IN (?, ?)", (token_hash(token), raw))
