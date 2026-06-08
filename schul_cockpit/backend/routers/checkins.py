from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..audit import (
    log as audit_log,
    snapshot_caught_up,
    snapshot_checkin,
)
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn

router = APIRouter()


class CheckinIn(BaseModel):
    # 1 = nicht verstanden, 2 = teilweise, 3 = verstanden,
    # 4 = nur Aufsicht / kein neuer Stoff (zählt nicht als Verständnis)
    rating: int = Field(ge=1, le=4)
    note: str | None = None


class CaughtUpIn(BaseModel):
    note: str | None = None


def _period_id_or_404(account_id: int, lesson_id: int) -> int | None:
    """Verify the lesson belongs to the account and return its stable
    Untis period id (for durable referencing)."""
    conn = history_conn()
    try:
        row = conn.execute(
            "SELECT untis_period_id FROM lessons WHERE id = ? AND account_id = ?",
            (lesson_id, account_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Lesson not found for this account")
    return row["untis_period_id"]


@router.post("/accounts/{account_id}/lessons/{lesson_id}/checkin")
def post_checkin(
    account_id: int,
    lesson_id: int,
    body: CheckinIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    period_id = _period_id_or_404(account_id, lesson_id)
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        before = snapshot_checkin(conn, account_id, lesson_id, user.id)
        conn.execute(
            "INSERT INTO lesson_checkins "
            "(account_id, lesson_id, user_id, rating, note, untis_period_id, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, lesson_id, user_id) DO UPDATE SET "
            "  rating = excluded.rating, "
            "  note = excluded.note, "
            "  untis_period_id = excluded.untis_period_id, "
            "  updated_at = excluded.updated_at",
            (account_id, lesson_id, user.id, body.rating, body.note, period_id, now, now),
        )
        after = snapshot_checkin(conn, account_id, lesson_id, user.id)
        audit_log(
            conn,
            user_id=user.id,
            account_id=account_id,
            op_type="insert" if before is None else "update",
            target_kind="checkin",
            target_id=after["id"] if after else None,
            label=f"Check-in Stunde #{lesson_id} → {body.rating}",
            before=before,
            after=after,
        )
    finally:
        conn.close()
    return {"ok": True, "lesson_id": lesson_id, "rating": body.rating}


@router.delete("/accounts/{account_id}/lessons/{lesson_id}/checkin")
def delete_checkin(
    account_id: int,
    lesson_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    conn = webapp_conn()
    try:
        before = snapshot_checkin(conn, account_id, lesson_id, user.id)
        conn.execute(
            "DELETE FROM lesson_checkins "
            "WHERE account_id = ? AND lesson_id = ? AND user_id = ?",
            (account_id, lesson_id, user.id),
        )
        if before:
            audit_log(
                conn,
                user_id=user.id,
                account_id=account_id,
                op_type="delete",
                target_kind="checkin",
                target_id=before["id"],
                label=f"Check-in Stunde #{lesson_id} entfernt",
                before=before,
            )
    finally:
        conn.close()
    return {"ok": True}


@router.post("/accounts/{account_id}/lessons/{lesson_id}/caught-up")
def post_caught_up(
    account_id: int,
    lesson_id: int,
    body: CaughtUpIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    period_id = _period_id_or_404(account_id, lesson_id)
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        before = snapshot_caught_up(conn, account_id, lesson_id, user.id)
        conn.execute(
            "INSERT INTO caught_up "
            "(account_id, lesson_id, user_id, caught_up_at, note, untis_period_id) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, lesson_id, user_id) DO UPDATE SET "
            "  caught_up_at = excluded.caught_up_at, "
            "  note = excluded.note, "
            "  untis_period_id = excluded.untis_period_id",
            (account_id, lesson_id, user.id, now, body.note, period_id),
        )
        after = snapshot_caught_up(conn, account_id, lesson_id, user.id)
        audit_log(
            conn,
            user_id=user.id,
            account_id=account_id,
            op_type="insert" if before is None else "update",
            target_kind="caught_up",
            target_id=after["id"] if after else None,
            label=f"Stunde #{lesson_id} als nachgeholt markiert",
            before=before,
            after=after,
        )
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/accounts/{account_id}/lessons/{lesson_id}/caught-up")
def delete_caught_up(
    account_id: int,
    lesson_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    conn = webapp_conn()
    try:
        before = snapshot_caught_up(conn, account_id, lesson_id, user.id)
        conn.execute(
            "DELETE FROM caught_up "
            "WHERE account_id = ? AND lesson_id = ? AND user_id = ?",
            (account_id, lesson_id, user.id),
        )
        if before:
            audit_log(
                conn,
                user_id=user.id,
                account_id=account_id,
                op_type="delete",
                target_kind="caught_up",
                target_id=before["id"],
                label=f"Nachgeholt-Markierung Stunde #{lesson_id} entfernt",
                before=before,
            )
    finally:
        conn.close()
    return {"ok": True}
