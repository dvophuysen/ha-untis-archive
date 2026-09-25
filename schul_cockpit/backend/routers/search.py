from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import _fmt_hhmm

router = APIRouter()


def _fold(value) -> str:
    return str(value).casefold() if value is not None else ""


def _register(conn) -> None:
    conn.create_function("sc_fold", 1, _fold, deterministic=True)


@router.get("/accounts/{account_id}/search")
def search(
    account_id: int,
    q: str = Query(..., min_length=2),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    # Gesucht wird mit Pythons casefold statt SQLites LOWER/LIKE: LOWER kennt
    # nur ASCII („ÜBUNG“ fand „übung“ nicht), und % oder _ in der Eingabe
    # wirkten als Platzhalter. instr() vergleicht wörtlich.
    needle = _fold(q)
    conn = history_conn()
    try:
        _register(conn)
        rows = conn.execute(
            "SELECT id, date, start_time, subject_name, teacher_name, room, "
            "lstext, subst_text FROM lessons "
            "WHERE account_id = ? AND ("
            "  instr(sc_fold(lstext), ?) > 0 OR "
            "  instr(sc_fold(subst_text), ?) > 0 OR "
            "  instr(sc_fold(info), ?) > 0"
            ") "
            "ORDER BY date DESC, start_time DESC LIMIT 200",
            (account_id, needle, needle, needle),
        ).fetchall()
    finally:
        conn.close()

    note_rows = []
    wconn = webapp_conn()
    try:
        _register(wconn)
        for r in wconn.execute(
            "SELECT lesson_id, note FROM lesson_checkins "
            "WHERE account_id = ? AND note IS NOT NULL "
            "AND instr(sc_fold(note), ?) > 0",
            (account_id, needle),
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
                "match_source": "lstext" if needle in _fold(r["lstext"]) else (
                    "subst_text" if needle in _fold(r["subst_text"]) else "info"
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
