"""Eltern-Dashboard — Aggregator über alle verlinkten Kinder.

Bündelt pro Kind den Eltern-Überblick in einem Roundtrip: anstehende
Klausuren mit Lern-Ampel, Fächer mit Unterstützungsbedarf (`Mitlernen`),
offene Hausaufgaben und die Karte der Startseite (`board`, D166: Status,
was jetzt offen ist, Arbeiten, was sich abzeichnet).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from .. import family_board, lernstand, usage_report
from ..auth import CurrentUser, get_current_user, linked_account_ids
from ..view_mode import acts_as_parent
from ..learning import today_local
from ..db import history_conn, webapp_conn
from ..exams import account_subjects, resolve_exams

router = APIRouter()
_LOG = logging.getLogger(__name__)
# Themenlisten nachziehen, ohne die Startseite warten zu lassen: je Arbeit
# höchstens alle zehn Minuten, ein Modellaufruf nur bei geändertem Text.
_TOPICS_REFRESH: dict[tuple[int, str], float] = {}
_TOPICS_EVERY = 600.0
_BACKGROUND: set[asyncio.Task] = set()

# Mitlernen + Klausur-Score: 21 Tage ≈ 3 Schulwochen — robust gegen
# einzelne Ausreißer, ohne dass alte Stimmungen das Bild verfälschen.
COMPREHENSION_WINDOW_DAYS = 21
COMPREHENSION_MIN_CHECKINS = 3
COMPREHENSION_HARD_RATIO = 0.30
EXAM_RED_DAYS = 14
EXAM_ORANGE_DAYS = 21


# ---------- Helpers ------------------------------------------------------


def _exam_priority(days_until: int, learn_state: int | None, comp: dict | None) -> str:
    """Ampel red/orange/green aus Frist + Lernstand + Verständnis im Fach."""
    weak_learn = learn_state is None or learn_state <= 1
    hard_ratio = 0.0
    if comp and comp.get("total", 0) >= COMPREHENSION_MIN_CHECKINS:
        hard_ratio = comp["hard"] / comp["total"]
    weak_comp = hard_ratio >= COMPREHENSION_HARD_RATIO
    risky = weak_learn or weak_comp
    if days_until <= EXAM_RED_DAYS and risky:
        return "red"
    if days_until <= EXAM_ORANGE_DAYS and risky:
        return "orange"
    return "green"


def _hw_urgency(due_date: str | None, today: date) -> str | None:
    # A missing completion mark is not proof that homework was missed.
    if not due_date:
        return None
    try:
        d = datetime.strptime(due_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    delta = (d - today).days
    if delta < 0:
        return "overdue"
    if delta == 0:
        return "red"
    if delta == 1:
        return "red"
    if delta <= 7:
        return "orange"
    return "green"


def _short_label(name: str | None, fallback_short: str | None) -> str:
    if fallback_short:
        return fallback_short
    if not name:
        return ""
    # Bei „Mathematik" → „Math", bei „Englisch" → „Engl" — kein Untis-Kürzel
    # vorhanden, aber besser als das volle Wort in der schmalen Spalte.
    cleaned = name.strip().split()[0] if name.strip() else ""
    return cleaned[:4]


def _comprehension_for_subjects(
    account_id: int, subject_ids: set[int]
) -> dict[int, dict]:
    """Pro Fach: {hard, total} an Checkins im 21-Tage-Fenster.
    `hard` zählt rating 1/2; `total` nur Verständnisbewertungen 1–3.
    Kommentare und reine Aufsicht sind keine Verständnisbewertungen."""
    out: dict[int, dict] = {sid: {"hard": 0, "total": 0} for sid in subject_ids}
    if not subject_ids:
        return out
    horizon = (today_local() - timedelta(days=COMPREHENSION_WINDOW_DAYS)).isoformat()
    today_iso = today_local().isoformat()
    hconn = history_conn()
    wconn = webapp_conn()
    try:
        placeholder = ",".join("?" for _ in subject_ids)
        lesson_rows = hconn.execute(
            f"SELECT id, subject_untis_id FROM lessons "
            f"WHERE account_id = ? AND subject_untis_id IN ({placeholder}) "
            f"  AND date >= ? AND date <= ? "
            f"  AND (code IS NULL OR LOWER(code) != 'cancelled')",
            [account_id, *subject_ids, horizon, today_iso],
        ).fetchall()
        if not lesson_rows:
            return out
        lesson_to_subject = {r["id"]: r["subject_untis_id"] for r in lesson_rows}
        lid_list = list(lesson_to_subject.keys())
        ph2 = ",".join("?" for _ in lid_list)
        rating_rows = wconn.execute(
            f"SELECT lesson_id, rating FROM lesson_checkins "
            f"WHERE account_id = ? AND lesson_id IN ({ph2})",
            [account_id, *lid_list],
        ).fetchall()
    finally:
        hconn.close()
        wconn.close()
    for r in rating_rows:
        sid = lesson_to_subject.get(r["lesson_id"])
        if sid is None or sid not in out or r["rating"] not in (1, 2, 3):
            continue
        out[sid]["total"] += 1
        if r["rating"] <= 2:
            out[sid]["hard"] += 1
    return out


# ---------- Endpoint -----------------------------------------------------


@router.get("/dashboard")
async def dashboard(user: CurrentUser = Depends(get_current_user)) -> dict:
    # Die Familienkarte mit „Beobachten“ ist nur für Eltern (Nutzerentscheidung).
    # Das Frontend ruft sie nur in der Elternansicht und im Testmodus auf.
    if not acts_as_parent(user):
        raise HTTPException(status_code=403, detail="Nur für Eltern.")
    today = today_local()
    today_iso = today.isoformat()
    account_ids = sorted(linked_account_ids(user.id))
    if not account_ids:
        return {"today": today_iso, "kids": []}

    hconn = history_conn()
    try:
        placeholder = ",".join("?" for _ in account_ids)
        name_rows = hconn.execute(
            f"SELECT id, name FROM accounts WHERE id IN ({placeholder}) ORDER BY name",
            account_ids,
        ).fetchall()
        names = {r["id"]: r["name"] for r in name_rows}
    finally:
        hconn.close()

    # Verwaiste Verlinkungen überspringen: zeigt ein Link auf eine
    # account_id, die es in der History-DB nicht (mehr) gibt (ID-Shift
    # nach Schuljahreswechsel / Restore), gab es vorher eine namenlose
    # Geisterkarte im Dashboard. Die IDs melden wir separat, damit die
    # Oberfläche warnen kann statt still Unsinn anzuzeigen.
    stale_account_ids = [acc_id for acc_id in account_ids if acc_id not in names]
    # Die Kinder parallel: Kalender und Karte laufen je Kind unabhängig.
    kids = list(await asyncio.gather(*(
        _dashboard_for_account(acc_id, names[acc_id], today) for acc_id in account_ids if acc_id in names)))
    return {
        "today": today_iso,
        "kids": kids,
        "stale_account_ids": stale_account_ids,
    }


async def _dashboard_for_account(account_id: int, name: str, today: date) -> dict:
    today_iso = today.isoformat()

    subjects = account_subjects(account_id)
    short_by_id = {s["subject_untis_id"]: s.get("short") for s in subjects}
    name_by_id = {s["subject_untis_id"]: s["subject_name"] for s in subjects}
    all_subject_ids = {s["subject_untis_id"] for s in subjects}

    # Klausuren bis Schuljahresende (12 Monate Lookahead deckt das ab).
    exam_data = await resolve_exams(account_id, days_ahead=365, past_days=365)
    exams_raw = [e for e in exam_data["exams"] if e["date"] >= today_iso]
    exam_subject_ids = {
        e.get("subject_untis_id") for e in exams_raw if e.get("subject_untis_id")
    }

    comp_all = _comprehension_for_subjects(
        account_id, all_subject_ids | exam_subject_ids
    )

    wconn = webapp_conn()
    try:
        prog_rows = wconn.execute(
            "SELECT exam_key, learn_state FROM exam_progress WHERE account_id = ?",
            (account_id,),
        ).fetchall()
        learn_by_key = {r["exam_key"]: r["learn_state"] for r in prog_rows}
        task_rows = wconn.execute(
            "SELECT id, title, subject_untis_id, subject_name, due_date, task_type "
            "FROM tasks WHERE account_id = ? AND status IN ('open', 'in_progress') "
            "ORDER BY (due_date IS NULL), due_date, id",
            (account_id,),
        ).fetchall()
    finally:
        wconn.close()

    exams_out = []
    for e in exams_raw:
        sid = e.get("subject_untis_id")
        comp = comp_all.get(sid) if sid else None
        d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        days_until = (d - today).days
        learn = learn_by_key.get(e.get("exam_key"))
        exams_out.append({
            "exam_key": e.get("exam_key"),
            "date": e["date"],
            "days_until": days_until,
            "subject_id": sid,
            "subject_name": e.get("subject_name") or e.get("title"),
            "subject_short": _short_label(
                e.get("subject_name") or e.get("title"),
                short_by_id.get(sid),
            ),
            "title": e.get("title"),
            "learn_state": learn,
            "comprehension": comp,
            "priority": _exam_priority(days_until, learn, comp),
        })

    support = []
    for sid, comp in comp_all.items():
        if comp["total"] < COMPREHENSION_MIN_CHECKINS:
            continue
        if comp["hard"] / comp["total"] < COMPREHENSION_HARD_RATIO:
            continue
        support.append({
            "subject_id": sid,
            "subject_short": _short_label(name_by_id.get(sid), short_by_id.get(sid)),
            "subject_name": name_by_id.get(sid),
            "hard_count": comp["hard"],
            "total_count": comp["total"],
        })
    support.sort(key=lambda s: (-s["hard_count"], s["subject_name"] or ""))

    tasks_out = []
    for r in task_rows:
        tasks_out.append({
            "id": r["id"],
            "title": r["title"],
            "subject_short": _short_label(r["subject_name"], short_by_id.get(r["subject_untis_id"])),
            "subject_name": r["subject_name"],
            "due_date": r["due_date"],
            "task_type": r["task_type"],
            "urgency": _hw_urgency(r["due_date"], today),
        })

    _refresh_topics(account_id, exams_raw, exam_data["exams"], today)
    from .today import evening_from
    now = datetime.now(usage_report.TZ)
    board = await asyncio.to_thread(
        family_board.board, account_id, tasks_out, exams_raw, exam_data["exams"], support,
        today, now, evening_from(account_id))

    # Serie und neue Abzeichen des Kindes auf seiner Karte (D173), nie im Vergleich.
    rewards_brief = None
    try:
        from .. import rewards
        r = await asyncio.to_thread(rewards.summary, account_id, now)
        rewards_brief = {k: r[k] for k in ("streak", "total", "week", "today")}
        names = {b["key"]: (b["name"], b["emoji"]) for b in r["badges"]}
        rewards_brief["reached_today"] = [
            {"name": names.get(x["badge"], (x["badge"], ""))[0], "emoji": names.get(x["badge"], ("", ""))[1],
             "level": rewards.LEVELS[x["level"] - 1]} for x in r["reached_today"]]
    except Exception:
        _LOG.warning("Belohnung für Konto %s nicht lesbar", account_id, exc_info=True)

    # Lernen heute (D180), nur zur Information: Die App steuert selbst nach.
    study = None
    try:
        from .. import study_plan
        p = await asyncio.to_thread(study_plan.view, account_id, now.date(), store=False)
        if p["total"] or p["tight"]:
            study = {"done": p["done"], "total": p["total"], "tight": p["tight"][:1], "frozen": p["frozen"]}
    except Exception:
        _LOG.warning("Lernplan für Konto %s nicht lesbar", account_id, exc_info=True)

    # Stundenplan-Raster und Tagesstreifen stehen nicht mehr auf der Startseite
    # (D166); der Plan liegt unter Übersichten → Woche.
    try:
        from .profile import read as read_profile
        profile = read_profile(account_id)
    except Exception:
        profile = None
    return {
        "rewards": rewards_brief,
        "study": study,
        "profile": profile,
        "account_id": account_id,
        "name": name,
        "exams": exams_out,
        "support": support,
        "tasks": {"open_count": len(tasks_out), "items": tasks_out},
        "board": board,
    }


def _refresh_topics(account_id: int, upcoming: list[dict], entries: list[dict], today: date) -> None:
    from .exams import scope_start
    stamp = time.monotonic()
    for e in upcoming:
        key = (account_id, e.get("exam_key") or "")
        if not key[1] or (date.fromisoformat(e["date"]) - today).days > family_board.NEAR_DAYS:
            continue
        if stamp - _TOPICS_REFRESH.get(key, -1e9) < _TOPICS_EVERY:
            continue
        _TOPICS_REFRESH[key] = stamp
        since = scope_start(e.get("subject_name"), e["date"], entries)

        async def run(e=e, since=since):
            try:
                await lernstand.ensure_topics(account_id, e["exam_key"], e.get("subject_name"), since, e["date"])
            except Exception:
                _LOG.warning("Themenliste für %s nicht nachgezogen", e.get("subject_name"), exc_info=True)
        task = asyncio.get_running_loop().create_task(run())
        _BACKGROUND.add(task)
        task.add_done_callback(_BACKGROUND.discard)
