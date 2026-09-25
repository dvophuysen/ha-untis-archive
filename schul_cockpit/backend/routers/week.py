from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..courses import hidden_keys, lesson_is_hidden
from ..db import history_conn, webapp_conn
from ..queries import lessons_in_range

router = APIRouter()


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


@router.get("/accounts/{account_id}/week")
def week(
    account_id: int,
    start: str | None = Query(default=None, description="YYYY-MM-DD, defaults to current Mon"),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    if start:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="start muss ein Datum JJJJ-MM-TT sein") from None
    else:
        # Deutscher Kalendertag, nicht der des Servers (UTC im Container).
        from ..learning import today_local
        start_date = _monday_of(today_local())
    start_date = _monday_of(start_date)
    end_date = start_date + timedelta(days=6)

    conn = history_conn()
    try:
        lessons = lessons_in_range(
            conn, account_id, start_date.isoformat(), end_date.isoformat()
        )
    finally:
        conn.close()

    hidden = hidden_keys(account_id)
    lessons = [l for l in lessons if not lesson_is_hidden(l, hidden)]

    lesson_ids = [l["id"] for l in lessons]
    checkins: dict[int, dict] = {}
    caught_up: set[int] = set()
    if lesson_ids:
        wconn = webapp_conn()
        try:
            placeholder = ",".join("?" for _ in lesson_ids)
            for r in wconn.execute(
                f"SELECT lesson_id, rating, note FROM lesson_checkins "
                f"WHERE account_id = ? AND lesson_id IN ({placeholder})",
                [account_id, *lesson_ids],
            ).fetchall():
                checkins[r["lesson_id"]] = {"rating": r["rating"], "note": r["note"]}
            for r in wconn.execute(
                f"SELECT lesson_id FROM caught_up "
                f"WHERE account_id = ? AND lesson_id IN ({placeholder})",
                [account_id, *lesson_ids],
            ).fetchall():
                caught_up.add(r["lesson_id"])
        finally:
            wconn.close()

    try:
        from .. import sources
        sources.annotate_lessons(account_id, lessons)
    except Exception:
        pass
    for lesson in lessons:
        ck = checkins.get(lesson["id"])
        # `rating` is what the grid colour-codes; full `checkin` lets the
        # detail sheet pre-fill the comment field.
        lesson["rating"] = ck["rating"] if ck else None
        lesson["checkin"] = ck
        lesson["caught_up"] = lesson["id"] in caught_up

    return {
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "lessons": lessons,
    }


def _iso(value: str | None, name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name}: YYYY-MM-DD erwartet")


@router.get("/accounts/{account_id}/week/rolling")
async def week_rolling(
    account_id: int,
    from_: str | None = Query(default=None, alias="from", description="erster Tag, YYYY-MM-DD"),
    before: str | None = Query(default=None, description="die Schultage vor diesem Tag, YYYY-MM-DD"),
    days: int = Query(default=5, ge=1, le=10),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Die nächsten Schultage in einem Aufruf (D184): Leisten, Stunden,
    Abweichungen, Arbeiten mit Lernstand, Hausaufgaben, für Vergangenes der
    Rückblick. Ohne Parameter ab heute."""
    assert_account_access(user, account_id)
    from zoneinfo import ZoneInfo
    from .. import week_rolling as wr
    from ..learning import today_local
    now = datetime.now(ZoneInfo("Europe/Berlin")).replace(tzinfo=None)
    return await wr.rolling(account_id, today_local(), now, start=_iso(from_, "from"),
                            before=_iso(before, "before"), count=days)
