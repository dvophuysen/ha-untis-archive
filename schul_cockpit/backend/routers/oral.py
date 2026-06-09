"""Oral-participation helper: 'before the NEXT class of this subject, look
at the topics you struggled with recently'.

The previous version listed today's subjects — useless once the class had
already happened in the morning. Now we look forward: for each subject
that has a NEXT real lesson coming up (today still ahead, or in the next
N days), surface the most recent rough-going topics so the kid can
prepare in time.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import _fmt_hhmm, _subject_short_from_payload

router = APIRouter()


def _now_hhmm() -> int:
    n = datetime.now()
    return n.hour * 100 + n.minute


@router.get("/accounts/{account_id}/oral-suggestions")
def oral_suggestions(
    account_id: int,
    horizon_days: int = Query(default=7, ge=1, le=21),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    today = date.today()
    today_iso = today.isoformat()
    horizon_iso = (today + timedelta(days=horizon_days)).isoformat()
    now_hhmm = _now_hhmm()

    conn = history_conn()
    try:
        # Per subject, find the NEXT real (non-cancelled) lesson that
        # hasn't started yet — today after now_hhmm, or any later day up
        # to the horizon.
        upcoming = conn.execute(
            "SELECT subject_untis_id, subject_name, teacher_untis_id, teacher_name, "
            "  payload_json, date, start_time, end_time "
            "FROM lessons "
            "WHERE account_id = ? AND subject_untis_id IS NOT NULL "
            "  AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "  AND ( date > ? OR (date = ? AND start_time > ?) ) "
            "  AND date <= ? "
            "ORDER BY date, start_time",
            (account_id, today_iso, today_iso, now_hhmm, horizon_iso),
        ).fetchall()
    finally:
        conn.close()

    from ..courses import hidden_keys, lesson_is_hidden
    hidden = hidden_keys(account_id)

    # Keep only the EARLIEST upcoming (non-hidden) lesson per subject.
    next_per_subject: dict[int, dict] = {}
    for r in upcoming:
        if lesson_is_hidden(dict(r), hidden):
            continue
        sid = r["subject_untis_id"]
        if sid in next_per_subject:
            continue
        next_per_subject[sid] = {
            "subject_id": sid,
            "subject_name": r["subject_name"],
            "subject_short": _subject_short_from_payload(r["payload_json"]),
            "next_date": r["date"],
            "next_start_hhmm": _fmt_hhmm(r["start_time"]),
        }

    if not next_per_subject:
        return {"horizon_days": horizon_days, "groups": []}

    # Recent rough check-ins by this user (😟 or 😐). We look back ~6 weeks.
    horizon_back = (today - timedelta(days=42)).isoformat()
    wconn = webapp_conn()
    try:
        rough = wconn.execute(
            "SELECT lesson_id, rating, note FROM lesson_checkins "
            "WHERE account_id = ? AND user_id = ? AND rating <= 2 "
            "AND updated_at >= ? "
            "ORDER BY rating ASC, updated_at DESC LIMIT 150",
            (account_id, user.id, horizon_back),
        ).fetchall()
    finally:
        wconn.close()

    by_subject_items: dict[int, list[dict]] = defaultdict(list)

    if rough:
        rough_ids = [r["lesson_id"] for r in rough]
        conn = history_conn()
        try:
            placeholder = ",".join("?" for _ in rough_ids)
            lesson_meta = {
                row["id"]: row
                for row in conn.execute(
                    f"SELECT id, date, start_time, subject_untis_id, lstext "
                    f"FROM lessons WHERE id IN ({placeholder})",
                    rough_ids,
                ).fetchall()
            }
        finally:
            conn.close()

        for r in rough:
            meta = lesson_meta.get(r["lesson_id"])
            if not meta:
                continue
            sid = meta["subject_untis_id"]
            if sid not in next_per_subject:
                continue
            if len(by_subject_items[sid]) >= 3:
                continue
            # Skip empty lstext entries — nothing to revise.
            if not (meta["lstext"] or r["note"]):
                continue
            by_subject_items[sid].append(
                {
                    "lesson_id": meta["id"],
                    "date": meta["date"],
                    "start_hhmm": _fmt_hhmm(meta["start_time"]),
                    "rating": r["rating"],
                    "note": r["note"],
                    "lstext": (meta["lstext"] or "")[:240],
                }
            )

    # Build groups in order of urgency (earliest next lesson first), and
    # drop subjects with no rough topics to revise (they're noise).
    groups = []
    for sid, info in next_per_subject.items():
        items = by_subject_items.get(sid, [])
        if not items:
            continue
        try:
            d = datetime.strptime(info["next_date"], "%Y-%m-%d").date()
            days_until = (d - today).days
        except (ValueError, TypeError):
            days_until = 99
        groups.append({
            **info,
            "days_until_next": days_until,
            "items": items,
        })
    groups.sort(key=lambda g: (g["days_until_next"], g["next_start_hhmm"] or ""))
    return {"horizon_days": horizon_days, "groups": groups}
