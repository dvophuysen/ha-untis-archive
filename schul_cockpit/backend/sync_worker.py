"""Bidirectional sync between HA todo lists and the app's tasks table.

The Untis→HA-ToDo automation runs in HA and is untouched. We sync:
  - Ingress: new HA todo items → INSERT rows into `tasks` (source='ha_todo')
  - Mark-done from HA → UPDATE tasks status to 'done'
  - Mark-done in app → push update_item(status='completed') to HA

Dedup key from HA-side is the item's `uid`. Conflict resolution is
last-write-wins via timestamps.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import suppress
from datetime import datetime, timezone

from .db import webapp_conn
from .supervisor_client import SupervisorClient, SupervisorError, get_supervisor

_LOGGER = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_due(due: str | None) -> tuple[str | None, str | None]:
    """HA todo `due` can be a date (YYYY-MM-DD) or a datetime. Return
    (date, time) where time is HH:MM or None for all-day items."""
    if not due:
        return None, None
    due = str(due)
    if "T" in due:
        date_part, _, time_part = due.partition("T")
        return date_part or None, time_part[:5] if time_part else None
    if " " in due:
        date_part, _, time_part = due.partition(" ")
        return date_part or None, time_part[:5] if time_part else None
    return due, None


def _get_account_lists(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    return [
        (r["account_id"], r["ha_entity_id"])
        for r in conn.execute(
            "SELECT account_id, ha_entity_id FROM account_todo_lists"
        ).fetchall()
    ]


async def _sync_one(account_id: int, entity_id: str, sup: SupervisorClient) -> None:
    try:
        ha_items = await sup.get_todo_items(entity_id)
    except SupervisorError as exc:
        _LOGGER.warning("todo.get_items %s failed: %s", entity_id, exc)
        return

    now = _now()
    conn = webapp_conn()
    try:
        existing = {
            r["ha_uid"]: dict(r)
            for r in conn.execute(
                "SELECT id, ha_uid, status, updated_at, completed_at, title, "
                "due_date, due_time, notes "
                "FROM tasks WHERE account_id = ? AND ha_uid IS NOT NULL",
                (account_id,),
            ).fetchall()
        }

        ha_seen_uids: set[str] = set()

        for item in ha_items:
            uid = item.get("uid") or item.get("summary")
            if not uid:
                continue
            ha_seen_uids.add(uid)
            ha_status = item.get("status", "needs_action")
            ha_summary = item.get("summary") or ""
            ha_description = item.get("description") or None
            ha_due_date, ha_due_time = _split_due(item.get("due"))

            new_status = "done" if ha_status == "completed" else "open"

            row = existing.get(uid)
            if row is None:
                conn.execute(
                    "INSERT INTO tasks "
                    "(account_id, ha_uid, title, task_type, status, due_date, "
                    " due_time, notes, source, created_at, updated_at, "
                    " completed_at, ha_last_synced_at) "
                    "VALUES (?, ?, ?, 'homework', ?, ?, ?, ?, 'ha_todo', ?, ?, ?, ?)",
                    (
                        account_id,
                        uid,
                        ha_summary,
                        new_status,
                        ha_due_date,
                        ha_due_time,
                        ha_description,
                        now,
                        now,
                        now if new_status == "done" else None,
                        now,
                    ),
                )
                continue

            updates: list[tuple[str, str | None]] = []
            push_done_to_ha = False
            if row["status"] != new_status:
                # Conflict resolution:
                #   App=done, HA=needs_action → App wins. The user just
                #     ticked it off here; HA may still report the old state
                #     for a moment due to the eventual-consistency lag.
                #     We push 'completed' to HA below instead of reverting
                #     the local state.
                #   App=open, HA=completed → HA wins. The item was ticked
                #     off externally (HA UI, another device, automation),
                #     so we mirror that into the app.
                if row["status"] == "open" and new_status == "done":
                    updates.append(("status", "done"))
                    updates.append(("completed_at", now))
                elif row["status"] == "done" and new_status == "open":
                    push_done_to_ha = True

            # Untis owns title + due date: keep them authoritative on every
            # sync (the app cannot override them). Notes/description fill in
            # only when still empty so a user's own note is never clobbered.
            if (row.get("title") or "") != ha_summary and ha_summary:
                updates.append(("title", ha_summary))
            if (row.get("due_date") or None) != ha_due_date:
                updates.append(("due_date", ha_due_date))
            if (row.get("due_time") or None) != ha_due_time:
                updates.append(("due_time", ha_due_time))
            if ha_description and not (row.get("notes") or ""):
                updates.append(("notes", ha_description))

            if updates:
                set_clause = ", ".join(f"{c} = ?" for c, _ in updates) + ", updated_at = ?, ha_last_synced_at = ?"
                params = [v for _, v in updates] + [now, now, row["id"]]
                conn.execute(
                    f"UPDATE tasks SET {set_clause} WHERE id = ?",
                    params,
                )
            else:
                conn.execute(
                    "UPDATE tasks SET ha_last_synced_at = ? WHERE id = ?",
                    (now, row["id"]),
                )

            if push_done_to_ha:
                try:
                    await sup.update_todo_item(
                        entity_id,
                        row["title"],
                        status="completed",
                    )
                except SupervisorError as exc:
                    _LOGGER.warning(
                        "todo.update_item %s for %s failed: %s",
                        entity_id, row["title"], exc,
                    )

        for uid, row in existing.items():
            if uid in ha_seen_uids:
                continue
            if row["status"] == "done":
                last_sync = row.get("ha_last_synced_at") or row["updated_at"]
                if row["updated_at"] and row["updated_at"] > last_sync:
                    try:
                        await sup.update_todo_item(
                            entity_id,
                            row["title"],
                            status="completed",
                        )
                        conn.execute(
                            "UPDATE tasks SET ha_last_synced_at = ? WHERE id = ?",
                            (now, row["id"]),
                        )
                    except SupervisorError as exc:
                        _LOGGER.warning(
                            "todo.update_item %s for %s failed: %s",
                            entity_id, row["title"], exc,
                        )
    finally:
        conn.close()


async def sync_account(account_id: int) -> None:
    sup = get_supervisor()
    if not sup.available:
        return
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT ha_entity_id FROM account_todo_lists WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return
    await _sync_one(account_id, row["ha_entity_id"], sup)


async def sync_all() -> None:
    sup = get_supervisor()
    if not sup.available:
        return
    conn = webapp_conn()
    try:
        pairs = _get_account_lists(conn)
    finally:
        conn.close()
    for account_id, entity_id in pairs:
        await _sync_one(account_id, entity_id, sup)


async def background_sync_loop() -> None:
    while True:
        with suppress(asyncio.CancelledError):
            try:
                await sync_all()
            except Exception:
                _LOGGER.exception("Background HA-todo sync failed")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
