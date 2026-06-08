from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import lessons_for_date, upcoming_exams

router = APIRouter()


@router.get("/accounts/{account_id}/today")
def today(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    today_iso = date.today().isoformat()
    conn = history_conn()
    try:
        lessons = lessons_for_date(conn, account_id, today_iso)
        exams = upcoming_exams(conn, account_id, days_ahead=7)
    finally:
        conn.close()

    lesson_ids = [lesson_row["id"] for lesson_row in lessons]
    checkins_by_lesson: dict[int, dict] = {}
    caught_up_lessons: set[int] = set()
    if lesson_ids:
        wconn = webapp_conn()
        try:
            placeholder = ",".join("?" for _ in lesson_ids)
            for r in wconn.execute(
                f"SELECT lesson_id, rating, note FROM lesson_checkins "
                f"WHERE account_id = ? AND user_id = ? AND lesson_id IN ({placeholder})",
                [account_id, user.id, *lesson_ids],
            ).fetchall():
                checkins_by_lesson[r["lesson_id"]] = {
                    "rating": r["rating"],
                    "note": r["note"],
                }
            for r in wconn.execute(
                f"SELECT lesson_id FROM caught_up "
                f"WHERE account_id = ? AND user_id = ? AND lesson_id IN ({placeholder})",
                [account_id, user.id, *lesson_ids],
            ).fetchall():
                caught_up_lessons.add(r["lesson_id"])
        finally:
            wconn.close()

    enriched = []
    unrated = 0
    for lesson in lessons:
        lid = lesson["id"]
        cin = checkins_by_lesson.get(lid)
        lesson["checkin"] = cin
        lesson["caught_up"] = lid in caught_up_lessons
        if cin is None and not lesson["is_cancelled"] and not lesson["was_absent"]:
            unrated += 1
        enriched.append(lesson)

    return {
        "date": today_iso,
        "lessons": enriched,
        "summary": {
            "unrated_lessons": unrated,
            "upcoming_exams_7d": len(exams),
        },
        "upcoming_exams": exams,
    }
