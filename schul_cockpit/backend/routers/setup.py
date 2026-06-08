"""Admin-only setup endpoints: list users/accounts and assign roles/links."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import history_conn, webapp_conn
from ..supervisor_client import SupervisorError, get_supervisor

router = APIRouter()


VALID_ROLES = {"admin", "parent", "child", "pending"}


class UserPatch(BaseModel):
    role: str | None = Field(default=None)
    display_name: str | None = None
    account_ids: list[int] | None = None  # full replace
    is_admin: bool | None = None


class TodoListIn(BaseModel):
    account_id: int
    ha_entity_id: str
    display_name: str | None = None


@router.get("/users")
def list_users(user: CurrentUser = Depends(get_current_user)) -> dict:
    require_admin(user)
    conn = webapp_conn()
    try:
        users = conn.execute(
            "SELECT id, ha_user_id, display_name, role, is_admin, "
            "first_seen_at, last_seen_at, "
            "(pin_hash IS NOT NULL) AS has_pin FROM users ORDER BY first_seen_at"
        ).fetchall()
        links = conn.execute(
            "SELECT user_id, account_id FROM user_account_links"
        ).fetchall()
    finally:
        conn.close()
    by_user: dict[int, list[int]] = {}
    for link in links:
        by_user.setdefault(link["user_id"], []).append(link["account_id"])
    return {
        "users": [
            {
                "id": u["id"],
                "ha_user_id": u["ha_user_id"],
                "display_name": u["display_name"],
                "role": u["role"],
                "is_admin": bool(u["is_admin"]),
                "first_seen_at": u["first_seen_at"],
                "last_seen_at": u["last_seen_at"],
                "has_pin": bool(u["has_pin"]),
                "account_ids": sorted(by_user.get(u["id"], [])),
            }
            for u in users
        ]
    }


@router.get("/accounts")
def list_accounts(user: CurrentUser = Depends(get_current_user)) -> dict:
    require_admin(user)
    conn = history_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, school, username FROM accounts ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return {
        "accounts": [
            {
                "id": r["id"],
                "name": r["name"],
                "school": r["school"],
                "username": r["username"],
            }
            for r in rows
        ]
    }


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    patch: UserPatch,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    if patch.role is not None and patch.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role; allowed: {sorted(VALID_ROLES)}")

    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT id, is_admin FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")

        if patch.is_admin is False and row["is_admin"] and user.id == user_id:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND id != ?",
                (user_id,),
            ).fetchone()[0]
            if remaining == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Refuse to demote the last admin",
                )

        fields = []
        params: list = []
        if patch.role is not None:
            fields.append("role = ?")
            params.append(patch.role)
        if patch.display_name is not None:
            fields.append("display_name = ?")
            params.append(patch.display_name)
        if patch.is_admin is not None:
            fields.append("is_admin = ?")
            params.append(1 if patch.is_admin else 0)
        if fields:
            params.append(user_id)
            conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params
            )

        if patch.account_ids is not None:
            conn.execute("DELETE FROM user_account_links WHERE user_id = ?", (user_id,))
            for aid in patch.account_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO user_account_links (user_id, account_id) "
                    "VALUES (?, ?)",
                    (user_id, aid),
                )

        return {"ok": True}
    finally:
        conn.close()


@router.get("/todo-entities")
async def list_todo_entities(user: CurrentUser = Depends(get_current_user)) -> dict:
    require_admin(user)
    sup = get_supervisor()
    if not sup.available:
        return {"available": False, "entities": []}
    try:
        entities = await sup.list_todo_entities()
    except SupervisorError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {
        "available": True,
        "entities": [
            {
                "entity_id": e["entity_id"],
                "friendly_name": (e.get("attributes") or {}).get("friendly_name"),
            }
            for e in entities
        ],
    }


@router.get("/todo-lists")
def list_account_todo_lists(user: CurrentUser = Depends(get_current_user)) -> dict:
    require_admin(user)
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT account_id, ha_entity_id, display_name, updated_at "
            "FROM account_todo_lists ORDER BY account_id"
        ).fetchall()
    finally:
        conn.close()
    return {
        "todo_lists": [
            {
                "account_id": r["account_id"],
                "ha_entity_id": r["ha_entity_id"],
                "display_name": r["display_name"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    }


@router.put("/todo-lists")
def upsert_account_todo_list(
    body: TodoListIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        conn.execute(
            "INSERT INTO account_todo_lists "
            "(account_id, ha_entity_id, display_name, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(account_id) DO UPDATE SET "
            "  ha_entity_id = excluded.ha_entity_id, "
            "  display_name = excluded.display_name, "
            "  updated_at = excluded.updated_at",
            (body.account_id, body.ha_entity_id, body.display_name, now),
        )
    finally:
        conn.close()
    return {"ok": True}
