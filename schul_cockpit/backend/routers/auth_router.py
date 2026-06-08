"""PIN-based login for direct (non-Ingress) access."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import webapp_conn
from ..pin_auth import (
    SESSION_COOKIE,
    SESSION_TTL_DAYS,
    PinError,
    clear_pin,
    create_session,
    delete_session,
    has_pin,
    set_pin,
    verify_pin,
)

router = APIRouter()


class LoginIn(BaseModel):
    user_id: int
    pin: str = Field(min_length=4, max_length=8)


class PinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=8)


@router.get("/auth/users")
def login_user_list() -> dict:
    """Public — lists users who have a PIN, for the login screen."""
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT id, display_name, role FROM users "
            "WHERE pin_hash IS NOT NULL "
            "ORDER BY (role = 'admin') DESC, display_name"
        ).fetchall()
    finally:
        conn.close()
    return {
        "users": [
            {"id": r["id"], "display_name": r["display_name"], "role": r["role"]}
            for r in rows
        ]
    }


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    conn = webapp_conn()
    try:
        try:
            ok = verify_pin(conn, body.user_id, body.pin)
        except PinError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.message)
        if not ok:
            raise HTTPException(status_code=401, detail="Falscher PIN")
        token, expires = create_session(conn, body.user_id)
    finally:
        conn.close()

    # Reverse-proxy aware: if the request reached us over HTTPS (directly or
    # via Cloudflare Tunnel / NGINX setting X-Forwarded-Proto), mark the
    # cookie Secure so it cannot leak over plain HTTP. In a local LAN-only
    # setup over HTTP, we must not set Secure or the browser drops the
    # cookie entirely.
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower()
    is_https = request.url.scheme == "https" or forwarded_proto == "https"

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path="/",
        secure=is_https,
    )
    return {"ok": True, "expires_at": expires.isoformat()}


@router.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        conn = webapp_conn()
        try:
            delete_session(conn, token)
        finally:
            conn.close()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.put("/users/{user_id}/pin")
def admin_set_pin(
    user_id: int,
    body: PinIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    conn = webapp_conn()
    try:
        exists = conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="user not found")
        try:
            set_pin(conn, user_id, body.pin)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/users/{user_id}/pin")
def admin_clear_pin(
    user_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    conn = webapp_conn()
    try:
        clear_pin(conn, user_id)
    finally:
        conn.close()
    return {"ok": True}


@router.get("/users/{user_id}/pin-status")
def admin_pin_status(
    user_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    conn = webapp_conn()
    try:
        return {"has_pin": has_pin(conn, user_id)}
    finally:
        conn.close()
