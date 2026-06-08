"""Absences overview: missed lessons grouped into contiguous blocks.

Two days of absence are merged into one block if the kid did not attend
school on any day in between — so a Thu+Fri absence and a following Mon+Tue
absence become a single block (the weekend bridges them), but if the kid
was present on the Monday the block splits there. Cancelled lessons are
ignored: there was no content to miss.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import _fmt_hhmm, _subject_short_from_payload

router = APIRouter()


def _next_day(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d").date() + timedelta(days=1)
    return d.isoformat()


@router.get("/accounts/{account_id}/absences")
def absences(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)

    conn = history_conn()
    try:
        rows = conn.execute(
            "SELECT id, date, start_time, end_time, subject_untis_id, subject_name, "
            "teacher_name, room, lstext, was_absent, absence_reason, payload_json "
            "FROM lessons WHERE account_id = ? "
            "AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "ORDER BY date, start_time, end_time",
            (account_id,),
        ).fetchall()
        absence_meta = conn.execute(
            "SELECT start_date, end_date, reason, is_excused FROM absences "
            "WHERE account_id = ? ORDER BY start_date",
            (account_id,),
        ).fetchall()
    finally:
        conn.close()

    # Dates where the kid attended at least one real lesson (block separators).
    present_dates: set[str] = {r["date"] for r in rows if not r["was_absent"]}

    missed_by_date: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["was_absent"]:
            missed_by_date[r["date"]].append(r)
    absent_dates = sorted(missed_by_date)
    if not absent_dates:
        return {"blocks": []}

    # caught-up status for this user.
    wconn = webapp_conn()
    try:
        caught = {
            row["lesson_id"]
            for row in wconn.execute(
                "SELECT lesson_id FROM caught_up WHERE account_id = ? AND user_id = ?",
                (account_id, user.id),
            ).fetchall()
        }
    finally:
        wconn.close()

    def _attended_between(d1: str, d2: str) -> bool:
        cur = _next_day(d1)
        while cur < d2:
            if cur in present_dates:
                return True
            cur = _next_day(cur)
        return False

    # Cluster absent dates into blocks.
    blocks: list[list[str]] = []
    for d in absent_dates:
        if blocks and not _attended_between(blocks[-1][-1], d):
            blocks[-1].append(d)
        else:
            blocks.append([d])

    def _reasons_for(start: str, end: str) -> tuple[list[str], bool]:
        reasons: list[str] = []
        all_excused = True
        any_match = False
        for m in absence_meta:
            # overlap test on [start_date, end_date] vs [start, end]
            if m["start_date"] <= end and m["end_date"] >= start:
                any_match = True
                if m["reason"] and m["reason"] not in reasons:
                    reasons.append(m["reason"])
                if not m["is_excused"]:
                    all_excused = False
        return reasons, (all_excused if any_match else False)

    result_blocks = []
    for dates in blocks:
        start, end = dates[0], dates[-1]
        lessons = []
        caught_count = 0
        for d in dates:
            for r in sorted(missed_by_date[d], key=lambda x: (x["start_time"] or 0)):
                is_caught = r["id"] in caught
                if is_caught:
                    caught_count += 1
                lessons.append(
                    {
                        "lesson_id": r["id"],
                        "date": r["date"],
                        "start_hhmm": _fmt_hhmm(r["start_time"]),
                        "subject_name": r["subject_name"],
                        "subject_short": _subject_short_from_payload(r["payload_json"]),
                        "teacher": r["teacher_name"],
                        "lstext": r["lstext"],
                        "caught_up": is_caught,
                    }
                )
        reasons, excused = _reasons_for(start, end)
        result_blocks.append(
            {
                "start": start,
                "end": end,
                "days": len(dates),
                "reasons": reasons,
                "is_excused": excused,
                "total": len(lessons),
                "caught_up_count": caught_count,
                "open_count": len(lessons) - caught_count,
                "lessons": lessons,
            }
        )

    # Newest block first.
    result_blocks.sort(key=lambda b: b["start"], reverse=True)
    return {"blocks": result_blocks}
