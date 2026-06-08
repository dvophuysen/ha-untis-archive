from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import _fmt_hhmm

router = APIRouter()


@router.get("/accounts/{account_id}/subjects")
def list_subjects(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    conn = history_conn()
    try:
        rows = conn.execute(
            "SELECT subject_untis_id, subject_name, COUNT(*) AS lessons_total "
            "FROM lessons WHERE account_id = ? AND subject_untis_id IS NOT NULL "
            "GROUP BY subject_untis_id, subject_name "
            "ORDER BY subject_name",
            (account_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "subjects": [
            {
                "subject_id": r["subject_untis_id"],
                "name": r["subject_name"],
                "lessons_total": r["lessons_total"],
            }
            for r in rows
        ]
    }


@router.get("/accounts/{account_id}/subjects/{subject_id}")
def subject_detail(
    account_id: int,
    subject_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    horizon = (date.today() - timedelta(days=120)).isoformat()
    conn = history_conn()
    try:
        info = conn.execute(
            "SELECT subject_name FROM lessons "
            "WHERE account_id = ? AND subject_untis_id = ? LIMIT 1",
            (account_id, subject_id),
        ).fetchone()
        if info is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        subject_name = info["subject_name"]
        rows = conn.execute(
            "SELECT id, date, start_time, teacher_name, room, code, "
            "lstext, was_absent, absence_reason "
            "FROM lessons "
            "WHERE account_id = ? AND subject_untis_id = ? AND date >= ? "
            "ORDER BY date DESC, start_time DESC",
            (account_id, subject_id, horizon),
        ).fetchall()
    finally:
        conn.close()

    lesson_ids = [r["id"] for r in rows]
    ratings: dict[int, dict] = {}
    if lesson_ids:
        wconn = webapp_conn()
        try:
            placeholder = ",".join("?" for _ in lesson_ids)
            for r in wconn.execute(
                f"SELECT lesson_id, rating, note FROM lesson_checkins "
                f"WHERE account_id = ? AND user_id = ? AND lesson_id IN ({placeholder})",
                [account_id, user.id, *lesson_ids],
            ).fetchall():
                ratings[r["lesson_id"]] = {"rating": r["rating"], "note": r["note"]}
        finally:
            wconn.close()

    timeline = []
    for r in rows:
        item = {
            "lesson_id": r["id"],
            "date": r["date"],
            "start_hhmm": _fmt_hhmm(r["start_time"]),
            "teacher": r["teacher_name"],
            "room": r["room"],
            "code": r["code"],
            "lstext": r["lstext"],
            "was_absent": bool(r["was_absent"]),
            "absence_reason": r["absence_reason"],
            "checkin": ratings.get(r["id"]),
        }
        timeline.append(item)

    return {
        "subject_id": subject_id,
        "name": subject_name,
        "timeline": timeline,
    }
