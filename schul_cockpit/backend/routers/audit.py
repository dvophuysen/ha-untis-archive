"""User-facing audit log: list + revert own changes, demo-mode toggle."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import CurrentUser, get_current_user, require_admin
from ..db import webapp_conn

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/my-changes")
def list_my_changes(
    limit: int = Query(default=100, ge=1, le=500),
    only_open: bool = Query(default=True, description="Only entries that have not been reverted"),
    demo_only: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    sql = "SELECT * FROM audit_log WHERE user_id = ?"
    params: list = [user.id]
    if only_open:
        sql += " AND reverted_at IS NULL"
    if demo_only:
        sql += " AND demo_mode = 1"
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    conn = webapp_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return {
        "entries": [
            {
                "id": r["id"],
                "op_type": r["op_type"],
                "target_kind": r["target_kind"],
                "target_id": r["target_id"],
                "account_id": r["account_id"],
                "label": r["label"],
                "demo_mode": bool(r["demo_mode"]),
                "created_at": r["created_at"],
                "reverted_at": r["reverted_at"],
            }
            for r in rows
        ]
    }


class DemoToggle(BaseModel):
    enabled: bool


@router.patch("/me/demo-mode")
def toggle_demo(
    body: DemoToggle,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    now = _now()
    conn = webapp_conn()
    try:
        if body.enabled:
            conn.execute(
                "UPDATE users SET demo_mode = 1, demo_started_at = ? WHERE id = ?",
                (now, user.id),
            )
        else:
            conn.execute(
                "UPDATE users SET demo_mode = 0, demo_started_at = NULL WHERE id = ?",
                (user.id,),
            )
    finally:
        conn.close()
    return {"ok": True, "demo_mode": body.enabled}


def _revert_entry(conn, entry: dict) -> None:
    kind = entry["target_kind"]
    op = entry["op_type"]
    before = json.loads(entry["before_json"]) if entry["before_json"] else None
    after = json.loads(entry["after_json"]) if entry["after_json"] else None

    if kind == "task":
        if op == "insert":
            conn.execute("DELETE FROM tasks WHERE id = ?", (after["id"],))
        elif op == "delete":
            _restore_row(conn, "tasks", before)
        elif op == "update":
            _update_columns(conn, "tasks", before, after)
        return

    if kind == "checkin":
        if op == "insert":
            conn.execute("DELETE FROM lesson_checkins WHERE id = ?", (after["id"],))
        elif op == "delete":
            _restore_row(conn, "lesson_checkins", before)
        elif op == "update":
            _update_columns(conn, "lesson_checkins", before, after)
        return

    if kind == "caught_up":
        if op == "insert":
            conn.execute("DELETE FROM caught_up WHERE id = ?", (after["id"],))
        elif op == "delete":
            _restore_row(conn, "caught_up", before)
        elif op == "update":
            _update_columns(conn, "caught_up", before, after)
        return

    if kind == "settings":
        if op == "insert":
            conn.execute("DELETE FROM account_settings WHERE account_id = ?", (after["account_id"],))
        elif op == "update":
            cols = [c for c in before if c != "account_id"]
            sets = ", ".join(f"{c} = ?" for c in cols)
            params = [before[c] for c in cols] + [before["account_id"]]
            conn.execute(f"UPDATE account_settings SET {sets} WHERE account_id = ?", params)
        return

    raise HTTPException(status_code=400, detail=f"Revert nicht unterstützt für {kind}/{op}")


def _restore_row(conn, table: str, snapshot: dict) -> None:
    cols = list(snapshot.keys())
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [snapshot[c] for c in cols],
    )


def _update_columns(conn, table: str, before: dict, after: dict) -> None:
    if not before:
        return
    pk_col = "account_id" if table == "account_settings" else "id"
    changed = [c for c in before if c != pk_col and before.get(c) != after.get(c)]
    if not changed:
        return
    sets = ", ".join(f"{c} = ?" for c in changed)
    params = [before[c] for c in changed] + [before[pk_col]]
    conn.execute(f"UPDATE {table} SET {sets} WHERE {pk_col} = ?", params)


@router.post("/my-changes/{entry_id}/revert")
def revert_entry(
    entry_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE id = ? AND user_id = ?",
            (entry_id, user.id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit-Eintrag nicht gefunden")
        if row["reverted_at"]:
            return {"ok": True, "already_reverted": True}
        _revert_entry(conn, dict(row))
        conn.execute(
            "UPDATE audit_log SET reverted_at = ? WHERE id = ?",
            (_now(), entry_id),
        )
    finally:
        conn.close()
    return {"ok": True}


@router.post("/my-changes/revert-all-demo")
def revert_all_demo(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Undo every still-open demo-mode entry of the current user.

    Iterates from newest to oldest so chained updates unwind correctly."""
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log "
            "WHERE user_id = ? AND demo_mode = 1 AND reverted_at IS NULL "
            "ORDER BY created_at DESC",
            (user.id,),
        ).fetchall()
        reverted = 0
        for r in rows:
            try:
                _revert_entry(conn, dict(r))
                conn.execute(
                    "UPDATE audit_log SET reverted_at = ? WHERE id = ?",
                    (_now(), r["id"]),
                )
                reverted += 1
            except Exception:
                pass
    finally:
        conn.close()
    return {"ok": True, "reverted": reverted}
