"""Auth resolution — two paths.

1. **HA Ingress headers** (X-Remote-User-Id / Name). Trusted only when the
   connection comes from the Supervisor's Ingress proxy (172.30.32.2); the
   direct port reaches the same listener, and there the headers are ignored.
   New users are auto-provisioned; the first one becomes admin.
2. **PIN session cookie** (sc_session). Used when the add-on is reached over
   its direct port — the path that makes an installable PWA + offline
   possible. Cookie is set by POST /api/auth/login after a valid PIN.

In development outside HA, DEV_FAKE_USER_ID / DEV_FAKE_USER_NAME simulate a
logged-in HA user.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from .config import SETTINGS
from .db import BUSY_TIMEOUT, webapp_conn
from .pin_auth import SESSION_COOKIE, lookup_session


@dataclass(frozen=True)
class CurrentUser:
    id: int
    ha_user_id: str
    display_name: str
    role: str
    is_admin: bool
    auth_source: str  # 'ingress' | 'pin'


LOG = logging.getLogger("schul_cockpit.auth")

# Der Ingress-Proxy des Supervisors spricht das Add-on immer von dieser Adresse
# an. Direktport, Tunnel und LAN erreichen denselben Port und können die
# Kopfzeilen frei setzen.
INGRESS_PEERS = frozenset(
    p.strip() for p in os.environ.get("WEBAPP_INGRESS_PEERS", "172.30.32.2").split(",") if p.strip()
)


def from_ingress(request) -> bool:
    """Ob die Anfrage unmittelbar vom Ingress-Proxy kommt. Maßgeblich ist die
    Gegenstelle der Verbindung, keine Kopfzeile; uvicorn läuft dafür ohne
    --proxy-headers, sonst stünde hier die Adresse aus X-Forwarded-For."""
    client = getattr(request, "client", None)
    return bool(client and client.host in INGRESS_PEERS)


def _headers_user(request: Request) -> tuple[str, str] | None:
    ha_user_id = request.headers.get("x-remote-user-id")
    ha_user_name = request.headers.get("x-remote-user-name") or ""
    if ha_user_id:
        if from_ingress(request):
            return ha_user_id, ha_user_name
        # Bis 1.13.11 galt die Kopfzeile von überall: Wer den Direktport
        # erreichte, war mit einer bekannten HA-Benutzer-ID ohne PIN angemeldet.
        client = getattr(request, "client", None)
        LOG.warning("Ingress-Kopfzeile von %s ignoriert (nicht vom Ingress-Proxy)",
                    client.host if client else "unbekannt")
    if SETTINGS.dev_fake_user_id:
        return SETTINGS.dev_fake_user_id, SETTINGS.dev_fake_user_name or "dev"
    return None


def _row_to_user(row, source: str) -> CurrentUser:
    return CurrentUser(
        id=row["id"],
        ha_user_id=row["ha_user_id"] or "",
        display_name=row["display_name"] or "",
        role=row["role"],
        is_admin=bool(row["is_admin"]),
        auth_source=source,
    )


# „Zuletzt gesehen“ wird höchstens so oft geschrieben (Minuten). Gelesen wird
# es nur in der Nutzerliste der Einrichtung; die Aktivitätsprüfung vor Updates
# (scripts/ha_activity.py) liest die Nutzungstage, nicht diesen Wert.
LAST_SEEN_EVERY = 2
# Wartezeit auf einen anderen Schreiber für diesen einen Nebenbei-Schreibzugriff
# in Millisekunden. Die Anfrage selbst soll nie darauf warten.
_SEEN_BUSY_MS = 200

_USER_COLS = "id, ha_user_id, display_name, role, is_admin, last_seen_at"


def _stale(stamp: str | None, now: datetime) -> bool:
    if not stamp:
        return True
    try:
        seen = datetime.fromisoformat(stamp)
    except ValueError:
        return True
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return now - seen >= timedelta(minutes=LAST_SEEN_EVERY)


def _touch(conn, sql: str, params: tuple) -> None:
    """Beiwerk schreiben, ohne dass die Anfrage daran hängt: kurze Wartezeit,
    eine gesperrte Datenbank wird übergangen."""
    try:
        conn.execute(f"PRAGMA busy_timeout = {_SEEN_BUSY_MS}")
        try:
            conn.execute(sql, params)
        finally:
            conn.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT * 1000)}")
    except sqlite3.OperationalError:
        pass


def _provision(conn, ha_user_id: str, ha_user_name: str, now: str) -> None:
    """Neuer Ingress-Nutzer. Zwei gleichzeitige erste Anfragen legten bis 1.31
    denselben Nutzer doppelt an (die zweite scheiterte am UNIQUE) oder machten
    zwei Nutzer zum Admin. Jetzt zählt und schreibt eine Transaktion."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        is_admin = 1 if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0 else 0
        conn.execute(
            "INSERT INTO users "
            "(ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(ha_user_id) DO NOTHING",
            (ha_user_id, ha_user_name, "admin" if is_admin else "pending", is_admin, now, now),
        )
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def get_current_user(request: Request) -> CurrentUser:
    """Resolve the current user from Ingress headers OR a PIN cookie."""
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    identified = _headers_user(request)

    conn = webapp_conn()
    try:
        if identified:
            ha_user_id, ha_user_name = identified
            row = conn.execute(
                f"SELECT {_USER_COLS} FROM users WHERE ha_user_id = ?", (ha_user_id,),
            ).fetchone()
            if row is None:
                _provision(conn, ha_user_id, ha_user_name, now)
                row = conn.execute(
                    f"SELECT {_USER_COLS} FROM users WHERE ha_user_id = ?", (ha_user_id,),
                ).fetchone()
            elif _stale(row["last_seen_at"], now_dt) or (ha_user_name and ha_user_name != row["display_name"]):
                # „Zuletzt gesehen" ist Beiwerk: Hält gerade ein anderer
                # Schreiber die Datei, darf daran keine Anfrage scheitern.
                _touch(conn,
                       "UPDATE users SET last_seen_at = ?, "
                       "display_name = COALESCE(NULLIF(?, ''), display_name) WHERE id = ?",
                       (now, ha_user_name, row["id"]))
                if ha_user_name and ha_user_name != row["display_name"]:
                    row = conn.execute(
                        f"SELECT {_USER_COLS} FROM users WHERE id = ?", (row["id"],),
                    ).fetchone()
            _mark(request, "ingress")
            return _row_to_user(row, "ingress")

        # No ingress identity → try the PIN session cookie.
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            user_id = lookup_session(conn, token)
            if user_id is not None:
                row = conn.execute(
                    f"SELECT {_USER_COLS} FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if row is not None:
                    if _stale(row["last_seen_at"], now_dt):
                        _touch(conn, "UPDATE users SET last_seen_at = ? WHERE id = ?", (now, row["id"]))
                    _mark(request, "pin", token)
                    return _row_to_user(row, "pin")

        raise HTTPException(status_code=401, detail="not authenticated")
    finally:
        conn.close()


def _mark(request, source: str, token: str | None = None) -> None:
    """Merkt an der Anfrage, wie sie angemeldet war. Die Middleware in main.py
    verlängert das Cookie nur für echte PIN-Anmeldungen."""
    state = getattr(request, "state", None)
    if state is None:
        return
    try:
        state.auth_source = source
        state.pin_token = token
    except Exception:
        pass


def require_admin(user: CurrentUser) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")


def linked_account_ids(user_id: int) -> set[int]:
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT account_id FROM user_account_links WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {row["account_id"] for row in rows}
    finally:
        conn.close()


def assert_account_access(user: CurrentUser, account_id: int) -> None:
    if user.is_admin:
        return
    if account_id not in linked_account_ids(user.id):
        raise HTTPException(status_code=403, detail="Account not linked to this user")
