from __future__ import annotations

from datetime import date, datetime, timezone

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
    # None records a comment without claiming a comprehension assessment.
    rating: int | None = Field(default=None, ge=1, le=4)
    note: str | None = None


class CaughtUpIn(BaseModel):
    note: str | None = None


def _lesson_or_404(account_id: int, lesson_id: int) -> dict:
    """Verify the lesson belongs to the account and return it (stable Untis
    period id for durable referencing, date and end for „vorbei?“)."""
    conn = history_conn()
    try:
        row = conn.execute(
            "SELECT * FROM lessons WHERE id = ? AND account_id = ?",
            (lesson_id, account_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Lesson not found for this account")
    return dict(row)


def _period_id_or_404(account_id: int, lesson_id: int) -> int | None:
    return _lesson_or_404(account_id, lesson_id).get("untis_period_id")


def _lesson_over(lesson: dict) -> bool:
    """Ist die Stunde vorbei? Dieselbe Regel wie die Wochenansicht
    (week_rolling._ended). Ohne Datum gilt sie als vorbei (alter Stand)."""
    day = lesson.get("date")
    if not day:
        return True
    from ..learning import today_local
    from ..rewards import now_local
    from ..week_rolling import _ended
    return _ended(lesson, str(day)[:10], today_local(), now_local())


@router.post("/accounts/{account_id}/lessons/{lesson_id}/checkin")
def post_checkin(
    account_id: int,
    lesson_id: int,
    body: CheckinIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    lesson = _lesson_or_404(account_id, lesson_id)
    period_id = lesson.get("untis_period_id")
    now = datetime.now(timezone.utc).isoformat()
    # Die Notiz ändert nur, wer sie mitschickt: eine Anfrage nur mit Notiz
    # (auch leer, zum Löschen) oder eine Bewertung mit Notiz. Eine Bewertung
    # ohne Notiz (fehlt oder null) ließ bis 1.31 eine vorhandene Notiz
    # verschwinden.
    keep_note = "note" not in body.model_fields_set or (body.note is None and body.rating is not None)
    conn = webapp_conn()
    try:
        before = snapshot_checkin(conn, account_id, lesson_id)
        conn.execute(
            "INSERT INTO lesson_checkins "
            "(account_id, lesson_id, user_id, rating, note, untis_period_id, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, lesson_id) DO UPDATE SET "
            "  rating = COALESCE(excluded.rating, lesson_checkins.rating), "
            + ("  note = lesson_checkins.note, " if keep_note else "  note = excluded.note, ") +
            "  user_id = excluded.user_id, "
            "  untis_period_id = excluded.untis_period_id, "
            "  updated_at = excluded.updated_at",
            (account_id, lesson_id, user.id, body.rating, body.note, period_id, now, now),
        )
        after = snapshot_checkin(conn, account_id, lesson_id)
        audit_log(
            conn,
            user_id=user.id,
            account_id=account_id,
            op_type="insert" if before is None else "update",
            target_kind="checkin",
            target_id=after["id"] if after else None,
            label=f"Check-in Stunde #{lesson_id}" if body.rating is not None else f"Kommentar Stunde #{lesson_id}",
            before=before,
            after=after,
        )
    finally:
        conn.close()
    if after and after["rating"] is not None:
        # Jede Rückmeldung zählt gleich, egal welches Gesicht (D173). Eine
        # Stunde, die noch nicht vorbei ist, zählt nicht: Die Bewertung wird
        # gespeichert, ein Ereignis gibt es erst für eine gehaltene Stunde.
        from .. import rewards
        if _lesson_over(lesson):
            rewards.note(account_id, "feedback", lesson_id, user)
    return {"ok": True, "lesson_id": lesson_id, "rating": after["rating"], "note": after["note"]}


@router.delete("/accounts/{account_id}/lessons/{lesson_id}/checkin")
def delete_checkin(
    account_id: int,
    lesson_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    conn = webapp_conn()
    try:
        before = snapshot_checkin(conn, account_id, lesson_id)
        conn.execute(
            "DELETE FROM lesson_checkins "
            "WHERE account_id = ? AND lesson_id = ?",
            (account_id, lesson_id),
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
        before = snapshot_caught_up(conn, account_id, lesson_id)
        conn.execute(
            "INSERT INTO caught_up "
            "(account_id, lesson_id, user_id, caught_up_at, note, untis_period_id) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, lesson_id) DO UPDATE SET "
            "  caught_up_at = excluded.caught_up_at, "
            "  note = excluded.note, "
            "  user_id = excluded.user_id, "
            "  untis_period_id = excluded.untis_period_id",
            (account_id, lesson_id, user.id, now, body.note, period_id),
        )
        after = snapshot_caught_up(conn, account_id, lesson_id)
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
        before = snapshot_caught_up(conn, account_id, lesson_id)
        conn.execute(
            "DELETE FROM caught_up "
            "WHERE account_id = ? AND lesson_id = ?",
            (account_id, lesson_id),
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


class WaiveIn(BaseModel):
    day: date


@router.post("/accounts/{account_id}/feedback/waive")
def waive_feedback(account_id: int, body: WaiveIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Eltern erlassen die offenen Rückmeldungen eines Tages, an dem das Kind
    nicht da war, ohne dass die Schule es führt (D210). Wie „entfällt“ bei
    Aufgaben nur für Eltern."""
    from .learning import access
    from .. import rewards
    access(user, account_id, write=True, parent=True)
    if body.day >= rewards.now_local().date():
        raise HTTPException(status_code=400, detail="Nur für vergangene Tage.")
    return {"waived": rewards.waive_feedback_day(account_id, body.day, user.id, rewards.now_local())}
