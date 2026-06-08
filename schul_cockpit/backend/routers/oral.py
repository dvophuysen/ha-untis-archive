"""Oral-participation helper: surface recently-confusing topics for today's subjects."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import _fmt_hhmm

router = APIRouter()


@router.get("/accounts/{account_id}/oral-suggestions")
def oral_suggestions(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    today_iso = date.today().isoformat()

    conn = history_conn()
    try:
        todays_subjects = {
            r["subject_untis_id"]: r["subject_name"]
            for r in conn.execute(
                "SELECT DISTINCT subject_untis_id, subject_name FROM lessons "
                "WHERE account_id = ? AND date = ? AND subject_untis_id IS NOT NULL "
                "AND (code IS NULL OR code = '' OR code = 'irregular')",
                (account_id, today_iso),
            ).fetchall()
        }
    finally:
        conn.close()

    if not todays_subjects:
        return {"date": today_iso, "groups": []}

    wconn = webapp_conn()
    try:
        rows = wconn.execute(
            "SELECT lesson_id, rating, note, updated_at FROM lesson_checkins "
            "WHERE account_id = ? AND user_id = ? AND rating <= 2 "
            "ORDER BY updated_at DESC LIMIT 100",
            (account_id, user.id),
        ).fetchall()
    finally:
        wconn.close()

    if not rows:
        return {"date": today_iso, "groups": [{"subject": n, "items": []} for n in todays_subjects.values()]}

    lesson_ids = [r["lesson_id"] for r in rows]
    conn = history_conn()
    try:
        placeholder = ",".join("?" for _ in lesson_ids)
        lesson_meta = {
            row["id"]: row
            for row in conn.execute(
                f"SELECT id, date, start_time, subject_untis_id, subject_name, lstext "
                f"FROM lessons WHERE id IN ({placeholder})",
                lesson_ids,
            ).fetchall()
        }
    finally:
        conn.close()

    by_subject: dict[int, list[dict]] = {sid: [] for sid in todays_subjects}
    for r in rows:
        meta = lesson_meta.get(r["lesson_id"])
        if not meta:
            continue
        sid = meta["subject_untis_id"]
        if sid not in by_subject:
            continue
        if len(by_subject[sid]) >= 3:
            continue
        by_subject[sid].append(
            {
                "lesson_id": meta["id"],
                "date": meta["date"],
                "start_hhmm": _fmt_hhmm(meta["start_time"]),
                "rating": r["rating"],
                "note": r["note"],
                "lstext": (meta["lstext"] or "")[:240],
            }
        )

    groups = []
    for sid, name in todays_subjects.items():
        groups.append({"subject": name, "subject_id": sid, "items": by_subject.get(sid, [])})
    return {"date": today_iso, "groups": groups}
