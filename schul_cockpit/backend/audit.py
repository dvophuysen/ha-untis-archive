"""Audit log: every mutating action records a before/after snapshot
so the acting user can review and undo their own changes."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, default=str, ensure_ascii=False)


def is_demo(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT demo_mode FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return bool(row and row["demo_mode"])


def log(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    account_id: int | None,
    op_type: str,                # 'insert' | 'update' | 'delete'
    target_kind: str,            # 'task' | 'subitem' | 'checkin' | 'caught_up' | 'settings' | 'todo_list'
    target_id: int | None,
    label: str | None = None,
    before: Any = None,
    after: Any = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO audit_log "
        "(user_id, account_id, op_type, target_kind, target_id, label, "
        " before_json, after_json, demo_mode, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            account_id,
            op_type,
            target_kind,
            target_id,
            label,
            _dump(before),
            _dump(after),
            1 if is_demo(conn, user_id) else 0,
            _now(),
        ),
    )
    return cur.lastrowid


def snapshot_task(conn: sqlite3.Connection, task_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def snapshot_checkin(
    conn: sqlite3.Connection, account_id: int, lesson_id: int, user_id: int
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM lesson_checkins "
        "WHERE account_id = ? AND lesson_id = ? AND user_id = ?",
        (account_id, lesson_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def snapshot_caught_up(
    conn: sqlite3.Connection, account_id: int, lesson_id: int, user_id: int
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM caught_up "
        "WHERE account_id = ? AND lesson_id = ? AND user_id = ?",
        (account_id, lesson_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def snapshot_settings(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM account_settings WHERE account_id = ?", (account_id,)
    ).fetchone()
    return dict(row) if row else None
