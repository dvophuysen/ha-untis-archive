"""Ingress authentication.

Home Assistant Ingress proxies the request and adds headers identifying the
HA user. We trust those headers because Ingress is the only network path
into the add-on (no port is exposed).

In development outside HA, the environment variables ``DEV_FAKE_USER_ID``
and ``DEV_FAKE_USER_NAME`` simulate a logged-in user.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from .config import SETTINGS
from .db import webapp_conn


@dataclass(frozen=True)
class CurrentUser:
    id: int
    ha_user_id: str
    display_name: str
    role: str
    is_admin: bool


def _headers_user(request: Request) -> tuple[str, str] | None:
    ha_user_id = request.headers.get("x-remote-user-id")
    ha_user_name = request.headers.get("x-remote-user-name") or ""
    if ha_user_id:
        return ha_user_id, ha_user_name
    if SETTINGS.dev_fake_user_id:
        return SETTINGS.dev_fake_user_id, SETTINGS.dev_fake_user_name or "dev"
    return None


def get_current_user(request: Request) -> CurrentUser:
    """Resolve the HA user from request headers, upserting into webapp.db.

    First-ever user becomes admin. Newly seen users are inserted as
    ``role='pending'`` so the admin can assign roles in the setup UI.
    """
    identified = _headers_user(request)
    if not identified:
        raise HTTPException(status_code=401, detail="No Ingress identity headers")
    ha_user_id, ha_user_name = identified

    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT id, ha_user_id, display_name, role, is_admin "
            "FROM users WHERE ha_user_id = ?",
            (ha_user_id,),
        ).fetchone()
        if row is None:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            is_admin = 1 if user_count == 0 else 0
            role = "admin" if is_admin else "pending"
            cur = conn.execute(
                "INSERT INTO users "
                "(ha_user_id, display_name, role, is_admin, first_seen_at, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ha_user_id, ha_user_name, role, is_admin, now, now),
            )
            user_id = cur.lastrowid
            display_name = ha_user_name
        else:
            user_id = row["id"]
            display_name = row["display_name"] or ha_user_name
            role = row["role"]
            is_admin = bool(row["is_admin"])
            conn.execute(
                "UPDATE users SET last_seen_at = ?, display_name = ? WHERE id = ?",
                (now, display_name, user_id),
            )
        return CurrentUser(
            id=user_id,
            ha_user_id=ha_user_id,
            display_name=display_name,
            role=role,
            is_admin=is_admin,
        )
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
