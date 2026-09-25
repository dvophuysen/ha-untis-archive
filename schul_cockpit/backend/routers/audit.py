"""User-facing audit log: list + revert own changes, demo-mode toggle."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import CurrentUser, assert_account_access, get_current_user, require_admin
from ..db import webapp_conn

router = APIRouter()
_LOG = logging.getLogger("schul_cockpit.audit")


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


class RevertConflict(Exception):
    """Der aktuelle Stand passt nicht mehr zum protokollierten Nachher."""


CONFLICT_DETAIL = ("Das wurde inzwischen noch einmal geändert. Rückgängig machen würde die "
                   "neuere Änderung überschreiben, deshalb bleibt es so.")
GONE_DETAIL = "Den Eintrag gibt es nicht mehr, es gibt nichts zurückzunehmen."

_ROW_TABLES = {"task": "tasks", "checkin": "lesson_checkins", "caught_up": "caught_up"}


def _same(a, b) -> bool:
    # Nach JSON zurückgelesen: 1 und 1.0 sind gleich, sonst wörtlich.
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return float(a) == float(b)
    return a == b


def _check_columns(current, after: dict, cols) -> None:
    if current is None:
        raise RevertConflict(GONE_DETAIL)
    for c in cols:
        if c in current.keys() and not _same(current[c], after.get(c)):
            raise RevertConflict(CONFLICT_DETAIL)


def _newer_entry(conn, entry: dict) -> bool:
    """Gibt es eine spätere, nicht zurückgenommene Änderung am selben Ziel?"""
    if entry.get("target_id") is None:
        return False
    return conn.execute(
        "SELECT 1 FROM audit_log WHERE target_kind = ? AND target_id = ? AND id > ? "
        "AND reverted_at IS NULL LIMIT 1",
        (entry["target_kind"], entry["target_id"], entry["id"]),
    ).fetchone() is not None


def _check_current(conn, entry: dict, before: dict | None, after: dict | None) -> None:
    """Zurückgenommen wird nur, solange der aktuelle Stand dem Nachher des
    Eintrags entspricht. Bis 1.31 überschrieb ein Rückgängig blind alles, was
    danach geändert worden war."""
    kind, op = entry["target_kind"], entry["op_type"]
    if kind in _ROW_TABLES:
        table = _ROW_TABLES[kind]
        if op == "update" and before:
            current = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (before["id"],)).fetchone()
            _check_columns(current, after or {}, [c for c in before if c != "id" and before.get(c) != (after or {}).get(c)])
        elif op == "insert" and after:
            if _newer_entry(conn, entry):
                raise RevertConflict(CONFLICT_DETAIL)
        elif op == "delete" and before:
            clash = conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (before["id"],)).fetchone()
            if clash is None and kind in ("checkin", "caught_up") and "lesson_id" in before:
                clash = conn.execute(
                    f"SELECT 1 FROM {table} WHERE account_id = ? AND lesson_id = ?",
                    (before.get("account_id"), before.get("lesson_id")),
                ).fetchone()
            if clash is not None:
                raise RevertConflict(CONFLICT_DETAIL)
        return
    if kind == "settings":
        if op == "update" and before:
            current = conn.execute("SELECT * FROM account_settings WHERE account_id = ?",
                                   (before["account_id"],)).fetchone()
            _check_columns(current, after or {}, [c for c in before if c != "account_id" and before.get(c) != (after or {}).get(c)])
        elif op == "insert" and _newer_entry(conn, entry):
            raise RevertConflict(CONFLICT_DETAIL)
        return
    if kind == "packing":
        key = after or before
        current = conn.execute(
            "SELECT * FROM packing_items WHERE account_id = ? AND school_day = ? AND item_key = ?",
            (key["account_id"], key["school_day"], key["item_key"]),
        ).fetchone()
        if op == "insert" or not before:
            if current is not None and after and not _same(current["done"], after.get("done")):
                raise RevertConflict(CONFLICT_DETAIL)
        else:
            _check_columns(current, after or {}, ["done"])


def _revert_entry(conn, entry: dict) -> None:
    kind = entry["target_kind"]
    op = entry["op_type"]
    before = json.loads(entry["before_json"]) if entry["before_json"] else None
    after = json.loads(entry["after_json"]) if entry["after_json"] else None
    _check_current(conn, entry, before, after)

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

    if kind == "packing":
        key = (after or before)
        where = "account_id = ? AND school_day = ? AND item_key = ?"
        params = (key["account_id"], key["school_day"], key["item_key"])
        if op == "insert" or not before:
            conn.execute(f"DELETE FROM packing_items WHERE {where}", params)
        else:
            conn.execute(f"UPDATE packing_items SET done = ?, revision = revision + 1, updated_at = ?, confirmed_by = ? WHERE {where}",
                         (before["done"], before["updated_at"], before.get("confirmed_by"), *params))
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


def _revert_in_tx(conn, entry_id: int, user_id: int) -> str:
    """Rücknahme und Vermerk in einer Transaktion. Liefert 'done',
    'already' oder wirft (RevertConflict, HTTPException)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE id = ? AND user_id = ?", (entry_id, user_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit-Eintrag nicht gefunden")
        if row["reverted_at"]:
            conn.execute("ROLLBACK")
            return "already"
        _revert_entry(conn, dict(row))
        conn.execute("UPDATE audit_log SET reverted_at = ? WHERE id = ?", (_now(), entry_id))
        conn.execute("COMMIT")
        return "done"
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


@router.post("/my-changes/{entry_id}/revert")
def revert_entry(
    entry_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT account_id FROM audit_log WHERE id = ? AND user_id = ?",
            (entry_id, user.id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit-Eintrag nicht gefunden")
        if row["account_id"] is not None:
            assert_account_access(user, row["account_id"])
        try:
            result = _revert_in_tx(conn, entry_id, user.id)
        except RevertConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    finally:
        conn.close()
    if result == "already":
        return {"ok": True, "already_reverted": True}
    return {"ok": True}


@router.post("/my-changes/revert-all-demo")
def revert_all_demo(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Undo every still-open demo-mode entry of the current user.

    Iterates from newest to oldest so chained updates unwind correctly. Jede
    Rücknahme steht in einer eigenen Transaktion; was inzwischen anders
    geändert wurde oder nicht zurückgeht, wird übersprungen und protokolliert,
    der Rest läuft weiter (Testmodus verlassen, D175)."""
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT id, account_id FROM audit_log "
            "WHERE user_id = ? AND demo_mode = 1 AND reverted_at IS NULL "
            "ORDER BY created_at DESC, id DESC",
            (user.id,),
        ).fetchall()
        reverted = skipped = 0
        for r in rows:
            try:
                if r["account_id"] is not None:
                    assert_account_access(user, r["account_id"])
                if _revert_in_tx(conn, r["id"], user.id) == "done":
                    reverted += 1
            except Exception as exc:
                skipped += 1
                _LOG.warning("Testmodus: Änderung %s nicht zurückgenommen: %s", r["id"],
                             getattr(exc, "detail", None) or exc)
    finally:
        conn.close()
    return {"ok": True, "reverted": reverted, "skipped": skipped}
