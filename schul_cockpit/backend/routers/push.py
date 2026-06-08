"""Web push: VAPID key exposure, subscribe/unsubscribe, send-test."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..auth import CurrentUser, get_current_user
from ..db import webapp_conn
from ..webpush_setup import ensure_keys, send_push

router = APIRouter()


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeIn(BaseModel):
    endpoint: str
    keys: SubKeys
    ua_label: str | None = None


@router.get("/push/vapid-key")
def vapid_key() -> dict:
    """Public — frontend uses this to subscribe at the browser's push service."""
    return {"public_key": ensure_keys()["public_b64url"]}


@router.post("/push/subscribe")
def subscribe(
    body: SubscribeIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        conn.execute(
            "INSERT INTO push_subscriptions "
            "(user_id, endpoint, p256dh, auth, ua_label, created_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "  user_id = excluded.user_id, "
            "  p256dh = excluded.p256dh, "
            "  auth = excluded.auth, "
            "  ua_label = COALESCE(excluded.ua_label, push_subscriptions.ua_label), "
            "  last_seen_at = excluded.last_seen_at",
            (
                user.id,
                body.endpoint,
                body.keys.p256dh,
                body.keys.auth,
                body.ua_label,
                now,
                now,
            ),
        )
    finally:
        conn.close()
    return {"ok": True}


@router.post("/push/unsubscribe")
def unsubscribe(
    body: dict,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    endpoint = body.get("endpoint")
    if not endpoint:
        return {"ok": True, "no_op": True}
    conn = webapp_conn()
    try:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
            (user.id, endpoint),
        )
    finally:
        conn.close()
    return {"ok": True}


@router.get("/push/devices")
def devices(user: CurrentUser = Depends(get_current_user)) -> dict:
    """List the current user's subscribed devices (for the settings page)."""
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT id, ua_label, created_at, last_seen_at FROM push_subscriptions "
            "WHERE user_id = ? ORDER BY last_seen_at DESC",
            (user.id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "devices": [
            {
                "id": r["id"],
                "label": r["ua_label"] or "Unbekanntes Gerät",
                "created_at": r["created_at"],
                "last_seen_at": r["last_seen_at"],
            }
            for r in rows
        ]
    }


@router.post("/push/test")
def send_test(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Send a test notification to all of the current user's devices."""
    conn = webapp_conn()
    try:
        subs = conn.execute(
            "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = ?",
            (user.id,),
        ).fetchall()
    finally:
        conn.close()
    if not subs:
        return {"ok": False, "reason": "no_subscriptions", "sent": 0}

    payload = {
        "title": "Schul-Cockpit",
        "body": "Test-Benachrichtigung — funktioniert!",
        "url": "./",
        "tag": "test",
    }
    sent = 0
    gone: list[int] = []
    for s in subs:
        sub_info = {
            "endpoint": s["endpoint"],
            "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
        }
        ok, status = send_push(sub_info, payload)
        if ok:
            sent += 1
        elif status in (404, 410):
            gone.append(s["id"])
    if gone:
        conn = webapp_conn()
        try:
            placeholder = ",".join("?" for _ in gone)
            conn.execute(
                f"DELETE FROM push_subscriptions WHERE id IN ({placeholder})", gone
            )
        finally:
            conn.close()
    return {"ok": True, "sent": sent, "removed_dead": len(gone)}
