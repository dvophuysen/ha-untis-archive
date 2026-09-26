from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from .. import day_close, request_cache
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
    # Lernplan und Ausblick lesen Raster und Pensum mehrfach: einmal je Aufruf.
    with request_cache.scope():
        return await _today(account_id, user)


async def _today(account_id: int, user) -> dict:
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
        # Freier Tag (Wochenende, Ferien): Rückmeldungen und Ringe zeigen den
        # Stand des letzten Schultags, wie die Lernliste (D205).
        carry_block: dict | None = None
        if not any(not l["is_cancelled"] and not l["was_absent"] for l in lessons):
            try:
                from ..study_plan import carry_day
                carry = carry_day(account_id, today_date)
            except Exception:
                carry = None
            if carry is not None:
                carry_block = {"date": carry.isoformat(), "lessons": [
                    l for l in lessons_for_date(conn, account_id, carry.isoformat())
                    if not lesson_is_hidden(l, hidden)]}
    finally:
        conn.close()

    lesson_ids = [lesson_row["id"] for lesson_row in lessons]
    if carry_block:
        lesson_ids += [l["id"] for l in carry_block["lessons"]]
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

    for lesson in (carry_block or {}).get("lessons", []):
        lesson["checkin"] = checkins_by_lesson.get(lesson["id"])
        lesson["caught_up"] = lesson["id"] in caught_up_lessons

    # Vergessene Rückmeldungen der Tage davor bleiben stehen, bis sie
    # nachgeholt sind (D210), wie überfällige Hausaufgaben.
    backlog: list[dict] = []
    try:
        from .. import rewards
        shown = date.fromisoformat(carry_block["date"]) if carry_block else today_date
        for lesson in rewards.feedback_backlog(account_id, shown - timedelta(days=1), rewards.now_local()):
            backlog.append({**lesson, "checkin": None, "caught_up": False})
    except Exception:
        import logging
        logging.getLogger("schul_cockpit.today").warning("Offene Rückmeldungen für Konto %s nicht lesbar", account_id, exc_info=True)

    return {
        "date": today_iso,
        "lessons": enriched,
        "carry_lessons": carry_block,
        "feedback_backlog": backlog,
        "summary": {
            "unrated_lessons": unrated,
            "upcoming_exams_7d": len(exams),
        },
        "upcoming_exams": exams,
        "next": next_block,
        "evening_from": evening_from(account_id),
        # Fürs Selbsteintragen (D174): an welchem Tag jedes Fach als Nächstes
        # Unterricht hat; dorthin schlägt die App den Termin vor.
        "next_by_subject": next_by_subject(account_id, today_date),
        # Vor einer Arbeit: Heftseiten, die der Unterricht nennt und die weder
        # digital noch fotografiert vorliegen. Höchstens drei Bitten.
        "photo_requests": await photo_requests(account_id, today_iso),
        # Seiten, die das Kind noch einmal fotografieren soll (D165).
        "retakes": _retakes(account_id),
        # Lern-Pflichtplan des Tages (D180), damit Heute mit einem Aufruf lädt (D177).
        "study_plan": _study_plan(account_id, user),
        "new_results": _new_results(account_id),
        # Ob der Tag schon durchgegangen wurde — davon hängt die Abendkarte ab
        # und am nächsten Morgen die zweite Mitteilung.
        "day_close": {
            "closed": day_close.closure(account_id, today_iso),
            "reliability": day_close.reliability(account_id, today_date),
        },
    }


def next_by_subject(account_id: int, today_date: date) -> dict[str, str]:
    try:
        from ..afternoon_check import _lessons_after
        found: dict[str, str] = {}
        for lesson in _lessons_after(account_id, today_date, 21):
            name = lesson.get("subject_name")
            if name and name not in found:
                found[name] = lesson["date"]
        return found
    except Exception:
        return {}


def _study_plan(account_id: int, user) -> dict | None:
    try:
        from .. import study_plan
        return study_plan.today(account_id, user)
    except Exception:
        import logging
        logging.getLogger("schul_cockpit.today").warning("Lernplan für Konto %s nicht lesbar", account_id, exc_info=True)
        return None


def _new_results(account_id: int) -> list[dict]:
    """Neu ausgewertete Übungsarbeiten, noch nicht angesehen (D201)."""
    try:
        from .practice import new_results
        return new_results(account_id)
    except Exception:
        return []


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
        found = (await resolve_exams(account_id, days_ahead=28)).get("exams", [])
        # Termine für den Lernplan (D180) merken, auch wenn die Klausurseite
        # noch nie geöffnet wurde; Fotobitten bleiben bei 14 Tagen.
        try:
            from .. import mentor_opening
            for e in found:
                if e.get("exam_key") and e.get("date"):
                    mentor_opening.remember_exam(account_id, e["exam_key"], e["date"])
        except Exception:
            pass
        from datetime import date as _date, timedelta as _td
        found = [e for e in found if (e.get("date") or "") <= (_date.fromisoformat(day) + _td(days=14)).isoformat()]
        try:
            # „Vorbereitet“ (D173): vor einer Arbeit alle Themen angefangen.
            from .. import rewards
            rewards.note_prepared(account_id, found)
        except Exception:
            pass
        return requests(account_id, found, day)
    except Exception:
        return []