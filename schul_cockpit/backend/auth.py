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
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from .config import SETTINGS
from .db import webapp_conn
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


def get_current_user(request: Request) -> CurrentUser:
    """Resolve the current user from Ingress headers OR a PIN cookie."""
    now = datetime.now(timezone.utc).isoformat()
    identified = _headers_user(request)

    conn = webapp_conn()
    try:
        if identified:
            ha_user_id, ha_user_name = identified
            row = conn.execute(
                "SELECT id, ha_user_id, display_name, role, is_admin "
                "FROM users WHERE ha_user_id = ?",
                (ha_user_id,),
            ).fetchone()
            if row is None:
                user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                is_admin = 1 if user_count == 0 else 0
                role = "admin" if is_admin else "pending"
                conn.execute(
                    "INSERT INTO users "
                    "(ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (ha_user_id, ha_user_name, role, is_admin, now, now),
                )
            else:
                # „Zuletzt gesehen" ist Beiwerk: Hält gerade ein anderer
                # Schreiber die Datei, darf daran keine Anfrage scheitern.
                try:
                    conn.execute(
                        "UPDATE users SET last_seen_at = ?, "
                        "display_name = COALESCE(NULLIF(?, ''), display_name) WHERE id = ?",
                        (now, ha_user_name, row["id"]),
                    )
                except sqlite3.OperationalError:
                    pass
            row = conn.execute(
                "SELECT id, ha_user_id, display_name, role, is_admin "
                "FROM users WHERE ha_user_id = ?",
                (ha_user_id,),
            ).fetchone()
            return _row_to_user(row, "ingress")

        # No ingress identity → try the PIN session cookie.
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            user_id = lookup_session(conn, token)
            if user_id is not None:
                row = conn.execute(
                    "SELECT id, ha_user_id, display_name, role, is_admin "
                    "FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if row is not None:
                    conn.execute(
                        "UPDATE users SET last_seen_at = ? WHERE id = ?",
                        (now, row["id"]),
                    )
                    return _row_to_user(row, "pin")

        raise HTTPException(status_code=401, detail="not authenticated")
    finally:
        conn.close()


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
