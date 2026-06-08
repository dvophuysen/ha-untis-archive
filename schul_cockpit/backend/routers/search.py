from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import _fmt_hhmm

router = APIRouter()


@router.get("/accounts/{account_id}/search")
def search(
    account_id: int,
    q: str = Query(..., min_length=2),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    pattern = f"%{q.lower()}%"
    conn = history_conn()
    try:
        rows = conn.execute(
            "SELECT id, date, start_time, subject_name, teacher_name, room, "
            "lstext, subst_text FROM lessons "
            "WHERE account_id = ? AND ("
            "  LOWER(IFNULL(lstext, '')) LIKE ? OR "
            "  LOWER(IFNULL(subst_text, '')) LIKE ? OR "
            "  LOWER(IFNULL(info, '')) LIKE ?"
            ") "
            "ORDER BY date DESC, start_time DESC LIMIT 200",
            (account_id, pattern, pattern, pattern),
        ).fetchall()
    finally:
        conn.close()

    note_rows = []
    wconn = webapp_conn()
    try:
        for r in wconn.execute(
            "SELECT lesson_id, note FROM lesson_checkins "
            "WHERE account_id = ? AND user_id = ? AND note IS NOT NULL "
            "AND LOWER(note) LIKE ?",
            (account_id, user.id, pattern),
        ).fetchall():
            note_rows.append(r)
    finally:
        wconn.close()

    hits = []
    for r in rows:
        hits.append(
            {
                "lesson_id": r["id"],
                "date": r["date"],
                "start_hhmm": _fmt_hhmm(r["start_time"]),
                "subject_name": r["subject_name"],
                "teacher": r["teacher_name"],
                "room": r["room"],
                "snippet": (r["lstext"] or r["subst_text"] or "")[:200],
                "match_source": "lstext" if r["lstext"] and q.lower() in r["lstext"].lower() else (
                    "subst_text" if r["subst_text"] and q.lower() in r["subst_text"].lower() else "info"
                ),
            }
        )

    grouped: dict[str, list[dict]] = {}
    for h in hits:
        grouped.setdefault(h["subject_name"] or "(ohne Fach)", []).append(h)

    return {
        "query": q,
        "groups": [
            {"subject": subject, "hits": entries}
            for subject, entries in sorted(grouped.items())
        ],
        "personal_note_hits": [{"lesson_id": r["lesson_id"], "note": r["note"]} for r in note_rows],
    }
