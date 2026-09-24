from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from .. import day_close
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..courses import hidden_keys, lesson_is_hidden
from ..learning import today_local
from ..db import history_conn, webapp_conn
from ..queries import lessons_for_date, upcoming_exams

router = APIRouter()

# Ab dieser Uhrzeit zählt nur noch, was für morgen fehlt. Dieselbe Zeit steuert
# die abendliche Erinnerung, damit Nachricht und Ansicht nicht auseinanderlaufen.
DEFAULT_EVENING = "18:00"


def evening_from(account_id: int) -> str:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT remind_at FROM reminder_settings WHERE account_id = ?", (account_id,)
        ).fetchone()
    finally:
        conn.close()
    return (row["remind_at"] if row and row["remind_at"] else DEFAULT_EVENING)


@router.get("/accounts/{account_id}/today")
async def today(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    today_date = today_local()
    today_iso = today_date.isoformat()
    conn = history_conn()
    try:
        lessons = lessons_for_date(conn, account_id, today_iso)
        exams = upcoming_exams(conn, account_id, days_ahead=7)
        hidden = hidden_keys(account_id)
        lessons = [l for l in lessons if not lesson_is_hidden(l, hidden)]

        # Nächster Schultag — für den Stundenplan-Block nach Schulschluss.
        # Wochenende, Ferien und ganz ausfallende Tage überspringen wir bis zu
        # 7 Tagen voraus.
        next_block: dict | None = None
        for offset in range(1, 8):
            cand_iso = (today_date + timedelta(days=offset)).isoformat()
            cand = [
                l for l in lessons_for_date(conn, account_id, cand_iso)
                if not lesson_is_hidden(l, hidden)
            ]
            # Ein Tag, an dem alles ausfällt, ist kein Schultag: die Tasche
            # gilt dann für den Tag danach (wie auf der Startseite, D166).
            if any(not l["is_cancelled"] and not l["was_absent"] for l in cand):
                for l in cand:
                    l["checkin"] = None
                    l["caught_up"] = False
                next_block = {"date": cand_iso, "lessons": cand}
                break
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
                f"WHERE account_id = ? AND lesson_id IN ({placeholder})",
                [account_id, *lesson_ids],
            ).fetchall():
                checkins_by_lesson[r["lesson_id"]] = {
                    "rating": r["rating"],
                    "note": r["note"],
                }
            for r in wconn.execute(
                f"SELECT lesson_id FROM caught_up "
                f"WHERE account_id = ? AND lesson_id IN ({placeholder})",
                [account_id, *lesson_ids],
            ).fetchall():
                caught_up_lessons.add(r["lesson_id"])
        finally:
            wconn.close()

    try:
        from .. import sources
        sources.annotate_lessons(account_id, lessons)
    except Exception:
        pass
    enriched = []
    unrated = 0
    for lesson in lessons:
        lid = lesson["id"]
        cin = checkins_by_lesson.get(lid)
        lesson["checkin"] = cin
        lesson["caught_up"] = lid in caught_up_lessons
        if (cin is None or cin["rating"] is None) and not lesson["is_cancelled"] and not lesson["was_absent"]:
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
        "next": next_block,
        "evening_from": evening_from(account_id),
        # Vor einer Arbeit: Heftseiten, die der Unterricht nennt und die weder
        # digital noch fotografiert vorliegen. Höchstens drei Bitten.
        "photo_requests": await photo_requests(account_id, today_iso),
        # Seiten, die das Kind noch einmal fotografieren soll (D165).
        "retakes": _retakes(account_id),
        # Ob der Tag schon durchgegangen wurde — davon hängt die Abendkarte ab
        # und am nächsten Morgen die zweite Mitteilung.
        "day_close": {
            "closed": day_close.closure(account_id, today_iso),
            "reliability": day_close.reliability(account_id, today_date),
        },
    }


def _retakes(account_id: int) -> list[dict]:
    try:
        from .. import materials as store
        return store.retakes(account_id)
    except Exception:
        return []


async def photo_requests(account_id: int, day: str) -> list[dict]:
    try:
        from ..exams import resolve_exams
        from ..sources import photo_requests as requests
        found = (await resolve_exams(account_id, days_ahead=14)).get("exams", [])
        return requests(account_id, found, day)
    except Exception:
        return []