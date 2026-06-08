"""Keep webapp.db's references to history.db durable.

webapp.db stores history.db's internal ids (accounts.id as account_id,
lessons.id as lesson_id). Those are stable across add-on updates and even
integration *code* updates, because history.db is keyed by stable Untis
identifiers (accounts.entry_id, lessons.untis_period_id) and persists.

They only change if the UNTIS Archive integration is fully removed and
re-added WITHOUT restoring history.db from backup, which re-numbers the
autoincrement ids. To survive that, we also store the stable keys and, on
every startup, reconcile:

1. accounts: maintain account_ref(entry_id -> account_id). If an entry_id
   now points to a different account_id, remap every account_id in
   webapp.db (collision-safe, two-phase).
2. lessons: backfill untis_period_id for rows that don't have it yet, then
   re-resolve lesson_id from (account_id, untis_period_id) where it drifted.

All of this is best-effort and wrapped so a failure never blocks startup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .db import history_conn, webapp_conn

_LOGGER = logging.getLogger("schul_cockpit.reconcile")

# Tables in webapp.db that carry an account_id and must be remapped together.
_ACCOUNT_TABLES = (
    "user_account_links",
    "account_todo_lists",
    "account_settings",
    "lesson_checkins",
    "caught_up",
    "tasks",
    "audit_log",
)

# Tables carrying (account_id, lesson_id, untis_period_id) lesson references.
_LESSON_TABLES = ("lesson_checkins", "caught_up", "tasks")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reconcile_all() -> None:
    try:
        _reconcile_accounts()
    except Exception:
        _LOGGER.exception("account reconcile failed (non-fatal)")
    try:
        _backfill_untis_period_ids()
        _reconcile_lessons()
    except Exception:
        _LOGGER.exception("lesson reconcile failed (non-fatal)")


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

def _reconcile_accounts() -> None:
    hist = history_conn()
    try:
        current = {
            r["entry_id"]: {"account_id": r["id"], "name": r["name"]}
            for r in hist.execute("SELECT id, entry_id, name FROM accounts").fetchall()
        }
    finally:
        hist.close()
    if not current:
        return

    conn = webapp_conn()
    try:
        known = {
            r["entry_id"]: {"account_id": r["account_id"]}
            for r in conn.execute(
                "SELECT entry_id, account_id FROM account_ref"
            ).fetchall()
        }

        # Detect remaps: same entry_id, different account_id than before.
        remaps: list[tuple[int, int]] = []  # (old, new)
        for entry_id, info in current.items():
            prev = known.get(entry_id)
            if prev and prev["account_id"] != info["account_id"]:
                remaps.append((prev["account_id"], info["account_id"]))

        if remaps:
            _LOGGER.warning(
                "UNTIS account ids changed (integration re-setup?). Remapping: %s",
                remaps,
            )
            _apply_account_remaps(conn, remaps)

        # Refresh the ref table to the current truth.
        now = _now()
        for entry_id, info in current.items():
            conn.execute(
                "INSERT INTO account_ref (entry_id, account_id, name, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(entry_id) DO UPDATE SET "
                "  account_id = excluded.account_id, "
                "  name = excluded.name, "
                "  updated_at = excluded.updated_at",
                (entry_id, info["account_id"], info["name"], now),
            )
    finally:
        conn.close()


def _apply_account_remaps(conn, remaps: list[tuple[int, int]]) -> None:
    """Remap account_id old->new across all tables, collision-safe.

    Two-phase via a large temporary offset so that a swap (1<->2) can't
    clobber rows mid-flight.
    """
    OFFSET = 1_000_000
    # Phase 1: old -> old+OFFSET (temporary, collision-free space)
    for old, _new in remaps:
        for table in _ACCOUNT_TABLES:
            conn.execute(
                f"UPDATE {table} SET account_id = account_id + ? WHERE account_id = ?",
                (OFFSET, old),
            )
    # Phase 2: old+OFFSET -> new
    for old, new in remaps:
        for table in _ACCOUNT_TABLES:
            conn.execute(
                f"UPDATE {table} SET account_id = ? WHERE account_id = ?",
                (new, old + OFFSET),
            )


# --------------------------------------------------------------------------
# Lessons
# --------------------------------------------------------------------------

def _backfill_untis_period_ids() -> None:
    """Fill untis_period_id for rows that only have lesson_id."""
    conn = webapp_conn()
    try:
        need: dict[str, list[int]] = {}
        for table in _LESSON_TABLES:
            rows = conn.execute(
                f"SELECT id, lesson_id FROM {table} "
                f"WHERE untis_period_id IS NULL AND lesson_id IS NOT NULL"
            ).fetchall()
            if rows:
                need[table] = [(r["id"], r["lesson_id"]) for r in rows]
        if not need:
            return

        all_lesson_ids = {lid for rows in need.values() for _, lid in rows}
        hist = history_conn()
        try:
            placeholder = ",".join("?" for _ in all_lesson_ids)
            period_by_lesson = {
                r["id"]: r["untis_period_id"]
                for r in hist.execute(
                    f"SELECT id, untis_period_id FROM lessons WHERE id IN ({placeholder})",
                    list(all_lesson_ids),
                ).fetchall()
            }
        finally:
            hist.close()

        for table, rows in need.items():
            for row_id, lesson_id in rows:
                pid = period_by_lesson.get(lesson_id)
                if pid is not None:
                    conn.execute(
                        f"UPDATE {table} SET untis_period_id = ? WHERE id = ?",
                        (pid, row_id),
                    )
    finally:
        conn.close()


def _reconcile_lessons() -> None:
    """Where lesson_id no longer matches the stored untis_period_id for the
    account, re-resolve lesson_id from history.db."""
    conn = webapp_conn()
    try:
        suspects: dict[str, list[tuple[int, int, int, int | None]]] = {}
        for table in _LESSON_TABLES:
            rows = conn.execute(
                f"SELECT id, account_id, untis_period_id, lesson_id FROM {table} "
                f"WHERE untis_period_id IS NOT NULL"
            ).fetchall()
            if rows:
                suspects[table] = [
                    (r["id"], r["account_id"], r["untis_period_id"], r["lesson_id"])
                    for r in rows
                ]
        if not suspects:
            return

        # Build (account_id, untis_period_id) -> current lesson.id map for the
        # period ids we care about.
        pairs = {
            (acc, pid)
            for rows in suspects.values()
            for _, acc, pid, _ in rows
        }
        hist = history_conn()
        try:
            resolved: dict[tuple[int, int], int] = {}
            for acc, pid in pairs:
                r = hist.execute(
                    "SELECT id FROM lessons WHERE account_id = ? AND untis_period_id = ?",
                    (acc, pid),
                ).fetchone()
                if r:
                    resolved[(acc, pid)] = r["id"]
        finally:
            hist.close()

        fixed = 0
        for table, rows in suspects.items():
            for row_id, acc, pid, current_lesson_id in rows:
                target = resolved.get((acc, pid))
                if target is not None and target != current_lesson_id:
                    conn.execute(
                        f"UPDATE {table} SET lesson_id = ? WHERE id = ?",
                        (target, row_id),
                    )
                    fixed += 1
        if fixed:
            _LOGGER.warning("Re-resolved %d lesson references after id drift", fixed)
    finally:
        conn.close()
