from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn

router = APIRouter()


class CheckinIn(BaseModel):
    rating: int = Field(ge=1, le=3)
    note: str | None = None


class CaughtUpIn(BaseModel):
    note: str | None = None


def _verify_lesson_exists(account_id: int, lesson_id: int) -> None:
    conn = history_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM lessons WHERE id = ? AND account_id = ?",
            (lesson_id, account_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Lesson not found for this account")


@router.post("/accounts/{account_id}/lessons/{lesson_id}/checkin")
def post_checkin(
    account_id: int,
    lesson_id: int,
    body: CheckinIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _verify_lesson_exists(account_id, lesson_id)
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        conn.execute(
            "INSERT INTO lesson_checkins "
            "(account_id, lesson_id, user_id, rating, note, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, lesson_id, user_id) DO UPDATE SET "
            "  rating = excluded.rating, "
            "  note = excluded.note, "
            "  updated_at = excluded.updated_at",
            (account_id, lesson_id, user.id, body.rating, body.note, now, now),
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
        conn.execute(
            "DELETE FROM lesson_checkins "
            "WHERE account_id = ? AND lesson_id = ? AND user_id = ?",
            (account_id, lesson_id, user.id),
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
    _verify_lesson_exists(account_id, lesson_id)
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        conn.execute(
            "INSERT INTO caught_up "
            "(account_id, lesson_id, user_id, caught_up_at, note) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, lesson_id, user_id) DO UPDATE SET "
            "  caught_up_at = excluded.caught_up_at, "
            "  note = excluded.note",
            (account_id, lesson_id, user.id, now, body.note),
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
        conn.execute(
            "DELETE FROM caught_up "
            "WHERE account_id = ? AND lesson_id = ? AND user_id = ?",
            (account_id, lesson_id, user.id),
        )
    finally:
        conn.close()
    return {"ok": True}
