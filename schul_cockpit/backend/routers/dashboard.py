"""Eltern-Dashboard — Aggregator über alle verlinkten Kinder.

Bündelt pro Kind den schnellen Eltern-Überblick in einem Roundtrip:
NOW-Streifen, anstehende Klausuren mit Lern-Ampel, Fächer mit
Unterstützungsbedarf (`Mitlernen`), offene Hausaufgaben, 5-Tage-Plan-Grid
und Feedback-Lücken. Die Ampel-Heuristik lebt hier zentral, damit
Eltern-Dashboard und Kinder-Klausurenseite denselben Punkt anzeigen.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user, linked_account_ids
from ..courses import hidden_keys, lesson_is_hidden
from ..db import history_conn, webapp_conn
from ..exams import account_subjects, resolve_exams
from ..queries import lessons_for_date, lessons_in_range

router = APIRouter()

# Mitlernen + Klausur-Score: 21 Tage ≈ 3 Schulwochen — robust gegen
# einzelne Ausreißer, ohne dass alte Stimmungen das Bild verfälschen.
COMPREHENSION_WINDOW_DAYS = 21
COMPREHENSION_MIN_CHECKINS = 3
COMPREHENSION_HARD_RATIO = 0.30
EXAM_RED_DAYS = 14
EXAM_ORANGE_DAYS = 21
FEEDBACK_GAP_DAYS = 7

_WEEKDAY_LABELS = ["Mo", "Di", "Mi", "Do", "Fr"]


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
    # Heute fällige Aufgabe = im Unterricht schon abgefragt → gescheitert.
    # Echte „rot" ist erst morgen (jetzt handeln, noch retten).
    if not due_date:
        return None
    try:
        d = datetime.strptime(due_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    delta = (d - today).days
    if delta <= 0:
        return "missed"
    if delta == 1:
        return "red"
    if delta <= 7:
        return "orange"
    return "green"


def _plan_columns(today: date) -> list[tuple[int, date, bool, bool]]:
    """Fünf Spalten Mo–Fr. Vergangene Wochentage rollen in die Folgewoche;
    am Wochenende rollt das gesamte Grid auf nächste Woche."""
    today_wd = today.weekday()  # Mo=0, So=6
    cols: list[tuple[int, date, bool, bool]] = []
    for col_wd in range(5):
        days_until = (col_wd - today_wd) % 7
        d = today + timedelta(days=days_until)
        if today_wd >= 5:
            # Wochenende → gesamte Woche ist „nächste".
            cols.append((col_wd, d, False, True))
        else:
            is_today = col_wd == today_wd
            is_filler = col_wd < today_wd  # dieser Wochentag ist schon vorbei
            cols.append((col_wd, d, is_today, is_filler))
    return cols


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
    `hard` zählt rating ≤ 2; `total` zählt alle abgegebenen Checkins."""
    out: dict[int, dict] = {sid: {"hard": 0, "total": 0} for sid in subject_ids}
    if not subject_ids:
        return out
    horizon = (date.today() - timedelta(days=COMPREHENSION_WINDOW_DAYS)).isoformat()
    today_iso = date.today().isoformat()
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
        if sid is None or sid not in out:
            continue
        out[sid]["total"] += 1
        if r["rating"] <= 2:
            out[sid]["hard"] += 1
    return out


def _now_state(account_id: int, today: date) -> dict:
    """Wo ist das Kind gerade? Schule / Pause / Schluss / Wochenende."""
    today_iso = today.isoformat()
    hconn = history_conn()
    try:
        rows = lessons_for_date(hconn, account_id, today_iso)
        hidden = hidden_keys(account_id)
        rows = [l for l in rows if not lesson_is_hidden(l, hidden)]
        real = [l for l in rows if not l.get("is_cancelled")]
        if not real:
            return _next_school_day_label(hconn, account_id, today)
    finally:
        hconn.close()

    now_hm = datetime.now().strftime("%H:%M")
    for l in real:
        s, e = l.get("start_hhmm"), l.get("end_hhmm")
        if s and e and s <= now_hm < e:
            return {
                "state": "in_school",
                "icon": "📚",
                "label": f"jetzt {l.get('subject_short') or l.get('subject_name') or '–'} · bis {e}",
            }
    first = real[0]
    if first.get("start_hhmm") and now_hm < first["start_hhmm"]:
        return {
            "state": "before_school",
            "icon": "📅",
            "label": f"Schule ab {first['start_hhmm']} · {first.get('subject_short') or first.get('subject_name') or ''}",
        }
    last = real[-1]
    return {
        "state": "after_school",
        "icon": "🏠",
        "label": f"Schulschluss {last.get('end_hhmm') or ''}".strip(),
    }


def _next_school_day_label(hconn, account_id: int, today: date) -> dict:
    hidden = hidden_keys(account_id)
    for offset in range(1, 8):
        d = today + timedelta(days=offset)
        rows = lessons_for_date(hconn, account_id, d.isoformat())
        rows = [
            l for l in rows
            if not lesson_is_hidden(l, hidden) and not l.get("is_cancelled")
        ]
        if not rows:
            continue
        first = sorted(rows, key=lambda x: x.get("start_hhmm") or "")[0]
        wd = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][d.weekday()]
        return {
            "state": "next_day",
            "icon": "📅",
            "label": f"nächste Schule {wd} {first.get('start_hhmm', '')} · "
                     f"{first.get('subject_short') or first.get('subject_name') or ''}",
        }
    return {"state": "no_school", "icon": "🌴", "label": "kein Schultag in Sicht"}


def _plan_for_account(account_id: int, today: date) -> dict:
    cols = _plan_columns(today)
    dates = [c[1] for c in cols]
    start_iso = min(dates).isoformat()
    end_iso = max(dates).isoformat()
    hconn = history_conn()
    try:
        lessons = lessons_in_range(hconn, account_id, start_iso, end_iso)
    finally:
        hconn.close()
    hidden = hidden_keys(account_id)
    lessons = [l for l in lessons if not lesson_is_hidden(l, hidden)]
    by_date: dict[str, list[dict]] = {}
    for l in lessons:
        by_date.setdefault(l["date"], []).append(l)

    def _cell(l: dict) -> dict:
        return {
            "lesson_id": l["id"],
            "start_hhmm": l.get("start_hhmm"),
            "end_hhmm": l.get("end_hhmm"),
            "subject_short": _short_label(l.get("subject_name"), l.get("subject_short")),
            "subject_name": l.get("subject_name"),
            "room": l.get("room"),
            "is_cancelled": bool(l.get("is_cancelled")),
            "is_irregular": bool(l.get("is_irregular")),
            "has_exam": bool(l.get("exam")),
        }

    columns = []
    for wd, d, is_today, is_filler in cols:
        day_lessons = sorted(
            (_cell(l) for l in by_date.get(d.isoformat(), [])),
            key=lambda x: x["start_hhmm"] or "",
        )
        columns.append({
            "weekday": _WEEKDAY_LABELS[wd],
            "date": d.isoformat(),
            "is_today": is_today,
            "is_filler": is_filler,
            "lessons": day_lessons,
        })
    return {"columns": columns, "is_weekend": today.weekday() >= 5}


def _feedback_gap(account_id: int, today: date) -> dict:
    """Stunden der letzten 7 Tage, die tatsächlich stattgefunden haben
    (nicht cancelled, Kind nicht abwesend) und noch keinen Checkin haben."""
    horizon = (today - timedelta(days=FEEDBACK_GAP_DAYS)).isoformat()
    today_iso = today.isoformat()
    hconn = history_conn()
    wconn = webapp_conn()
    try:
        lesson_rows = hconn.execute(
            "SELECT id FROM lessons WHERE account_id = ? "
            "AND date >= ? AND date <= ? "
            "AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "AND was_absent = 0",
            (account_id, horizon, today_iso),
        ).fetchall()
        ids = [r["id"] for r in lesson_rows]
        if not ids:
            return {"unrated_lessons": 0, "total_lessons": 0}
        placeholder = ",".join("?" for _ in ids)
        rated = wconn.execute(
            f"SELECT COUNT(DISTINCT lesson_id) AS c FROM lesson_checkins "
            f"WHERE account_id = ? AND lesson_id IN ({placeholder})",
            [account_id, *ids],
        ).fetchone()["c"]
    finally:
        hconn.close()
        wconn.close()
    return {"unrated_lessons": len(ids) - rated, "total_lessons": len(ids)}


# ---------- Endpoint -----------------------------------------------------


@router.get("/dashboard")
async def dashboard(user: CurrentUser = Depends(get_current_user)) -> dict:
    today = date.today()
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

    kids = []
    for acc_id in account_ids:
        kids.append(await _dashboard_for_account(acc_id, names.get(acc_id, ""), today))
    return {"today": today_iso, "kids": kids}


async def _dashboard_for_account(account_id: int, name: str, today: date) -> dict:
    today_iso = today.isoformat()

    subjects = account_subjects(account_id)
    short_by_id = {s["subject_untis_id"]: s.get("short") for s in subjects}
    name_by_id = {s["subject_untis_id"]: s["subject_name"] for s in subjects}
    all_subject_ids = {s["subject_untis_id"] for s in subjects}

    # Klausuren bis Schuljahresende (12 Monate Lookahead deckt das ab).
    exam_data = await resolve_exams(account_id, days_ahead=365)
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

    return {
        "account_id": account_id,
        "name": name,
        "now": _now_state(account_id, today),
        "exams": exams_out,
        "support": support,
        "tasks": {"open_count": len(tasks_out), "items": tasks_out},
        "plan": _plan_for_account(account_id, today),
        "feedback_gap": _feedback_gap(account_id, today),
    }
