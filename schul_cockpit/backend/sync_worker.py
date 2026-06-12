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
import re
import sqlite3
from contextlib import suppress
from datetime import datetime, timezone

from .db import webapp_conn
from .supervisor_client import SupervisorClient, SupervisorError, get_supervisor

_LOGGER = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 120

# Untis-Hausaufgaben-ID-Tag im Notes-Feld, z.B. [MA260611] = Mathe, gegeben
# am 11.06.26. Untis schreibt diesen Tag in JEDE Variante derselben Aufgabe
# (gleicher Code, egal wie oft die HA-Automation neue UIDs vergibt). Damit
# ist er der kanonische Dedup-Schlüssel — robuster als (title, due_date,
# notes), die sich mit Untis-Edits leise verschieben können.
_UNTIS_ID_RE = re.compile(r"\[([A-Za-zÄÖÜäöüß]{1,5}\d+)\]")


def _untis_id(notes: str | None) -> str | None:
    if not notes:
        return None
    m = _UNTIS_ID_RE.search(notes)
    return m.group(1).upper() if m else None


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


async def _sync_one(
    account_id: int, entity_id: str, sup: SupervisorClient
) -> dict[str, int]:
    """Sync one account's HA todo list into the app. Returns a small stats
    dict so the manual sync endpoint can give UI feedback (`inserted`,
    `orphans_deleted`, `duplicates_collapsed`)."""
    try:
        ha_items = await sup.get_todo_items(entity_id)
    except SupervisorError as exc:
        _LOGGER.warning("todo.get_items %s failed: %s", entity_id, exc)
        return {
            "inserted": 0,
            "orphans_deleted": 0,
            "duplicates_collapsed": 0,
            "rebound_to_done": 0,
        }

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
        stats = {
            "inserted": 0,
            "orphans_deleted": 0,
            "duplicates_collapsed": 0,
            "rebound_to_done": 0,
        }

        # Index existierender Reihen nach Untis-ID — wenn HA für dieselbe
        # Aufgabe eine neue UID schickt, finden wir die alte Reihe darüber
        # und re-binden sie, statt eine zweite Reihe anzulegen. Done-Status
        # gewinnt: eine abgehakte Reihe darf nicht durch neue UID-Lieferung
        # wieder auf "offen" springen.
        by_untis: dict[str, list[dict]] = {}
        for r in existing.values():
            tag = _untis_id(r.get("notes"))
            if tag:
                by_untis.setdefault(tag, []).append(r)

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
                # Vor dem Insert: gibt's schon eine Reihe mit derselben
                # Untis-Hausaufgaben-ID? Dann ist das dieselbe Aufgabe mit
                # neuer HA-UID. Re-binden, Status beibehalten (done bleibt
                # done), kein neues Aktiv-Duplikat erzeugen.
                tag = _untis_id(ha_description)
                target = None
                if tag and by_untis.get(tag):
                    candidates = by_untis[tag]
                    done = [r for r in candidates if r["status"] == "done"]
                    pool = done if done else candidates
                    target = max(pool, key=lambda r: r["updated_at"] or "")
                if target is not None:
                    old_uid = target["ha_uid"]
                    conn.execute(
                        "UPDATE tasks SET ha_uid = ?, ha_last_synced_at = ? "
                        "WHERE id = ?",
                        (uid, now, target["id"]),
                    )
                    existing.pop(old_uid, None)
                    target["ha_uid"] = uid
                    existing[uid] = target
                    stats["rebound_to_done"] += 1
                    continue
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
                stats["inserted"] += 1
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
            else:
                # Offene ha_todo-Zeile, die nicht mehr in HA steht → die
                # Quelle der Wahrheit hat sie entfernt (oder die Automation
                # hat eine neue UID für denselben Eintrag erzeugt). Weg
                # damit, sonst sammelt sich Müll an.
                conn.execute("DELETE FROM tasks WHERE id = ?", (row["id"],))
                stats["orphans_deleted"] += 1

        # Untis-ID Dedup (Cross-Status): alle ha_todo-Reihen mit derselben
        # Hausaufgaben-ID (z.B. [MA260611]) gehören zusammen, egal wie oft
        # die HA-Automation neue UIDs vergeben hat. Done schlägt offen —
        # eine abgehakte Aufgabe darf nicht durch neue UID-Lieferungen
        # wieder als aktiv auftauchen.
        all_rows = conn.execute(
            "SELECT id, ha_uid, status, notes, updated_at FROM tasks "
            "WHERE account_id = ? AND ha_uid IS NOT NULL",
            (account_id,),
        ).fetchall()
        groups: dict[str, list[sqlite3.Row]] = {}
        for r in all_rows:
            tag = _untis_id(r["notes"])
            if tag:
                groups.setdefault(tag, []).append(r)

        for tag, group in groups.items():
            if len(group) <= 1:
                continue
            done_rows = [r for r in group if r["status"] == "done"]
            pool = done_rows if done_rows else group
            keeper = max(pool, key=lambda r: r["updated_at"] or "")
            # Vor dem Rebind die anderen Reihen löschen — sonst kollidiert
            # die UNIQUE(account_id, ha_uid)-Constraint, weil die UID, die
            # wir dem Keeper geben wollen, noch in einer anderen Reihe der
            # Gruppe steckt.
            new_uid = None
            if keeper["ha_uid"] not in ha_seen_uids:
                new_uid = next(
                    (
                        r["ha_uid"] for r in group
                        if r["id"] != keeper["id"] and r["ha_uid"] in ha_seen_uids
                    ),
                    None,
                )
            for r in group:
                if r["id"] == keeper["id"]:
                    continue
                conn.execute("DELETE FROM tasks WHERE id = ?", (r["id"],))
                stats["duplicates_collapsed"] += 1
            if new_uid:
                conn.execute(
                    "UPDATE tasks SET ha_uid = ?, ha_last_synced_at = ? "
                    "WHERE id = ?",
                    (new_uid, now, keeper["id"]),
                )
        if (
            stats["duplicates_collapsed"]
            or stats["orphans_deleted"]
            or stats["rebound_to_done"]
        ):
            _LOGGER.info(
                "sync %s: +%d inserted, %d orphans, %d dup, %d done-rebinds",
                entity_id,
                stats["inserted"],
                stats["orphans_deleted"],
                stats["duplicates_collapsed"],
                stats["rebound_to_done"],
            )
    finally:
        conn.close()
    return stats


async def sync_account(account_id: int) -> dict[str, int]:
    """Trigger one sync round for a single account; returns stats so the
    manual-sync endpoint can give the UI feedback (`inserted`,
    `orphans_deleted`, `duplicates_collapsed`)."""
    empty = {
        "inserted": 0,
        "orphans_deleted": 0,
        "duplicates_collapsed": 0,
        "rebound_to_done": 0,
    }
    sup = get_supervisor()
    if not sup.available:
        return empty
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT ha_entity_id FROM account_todo_lists WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return empty
    return await _sync_one(account_id, row["ha_entity_id"], sup)


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
