"""Afternoon planner: prioritized list of tasks fitting into today's time budget."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import upcoming_exams

router = APIRouter()

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _budget_for_today(account_id: int, today: date) -> tuple[int, dict]:
    """Returns (minutes, source_info) where source_info describes how the
    value was derived — surfaced in the UI banner."""
    from ..erlass import (
        ERLASS_DAILY_MIN,
        erlass_budget_minutes,
        has_afternoon_school,
        resolve_section,
    )

    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT default_daily_budget_minutes, budget_overrides_json, "
            "auto_budget, school_section_override "
            "FROM account_settings WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()

    auto = True if row is None else bool(row["auto_budget"])
    override_section = row["school_section_override"] if row else None

    if auto:
        section, klasse_name, src = resolve_section(account_id, override_section)
        if section is None:
            # Fall back to the manual value so we don't return 0 minutes
            # while the admin assigns the right section.
            default = (row and row["default_daily_budget_minutes"]) or 60
            return default, {
                "source": "fallback_manual",
                "reason": "Klasse konnte nicht erkannt werden",
            }
        afternoon = has_afternoon_school(account_id, today)
        minutes = erlass_budget_minutes(section, today, has_afternoon=afternoon)
        return minutes, {
            "source": "erlass",
            "section": section,
            "section_source": src,
            "klasse_name": klasse_name,
            "weekend": today.weekday() >= 5,
            "afternoon_reduced": afternoon and today.weekday() < 5,
            "erlass_max_workday": ERLASS_DAILY_MIN[section],
        }

    # Manual override branch — unchanged behaviour from before.
    default = (row and row["default_daily_budget_minutes"]) or 60
    overrides_raw = row["budget_overrides_json"] if row else None
    info = {"source": "manual"}
    if not overrides_raw:
        return default, info
    try:
        overrides = json.loads(overrides_raw)
    except json.JSONDecodeError:
        return default, info
    key = WEEKDAY_KEYS[today.weekday()]
    val = overrides.get(key)
    if val is None:
        return default, info
    return int(val), {"source": "manual_override"}


def _priority(task: dict, today: date, exam_lookup: dict[int, date]) -> int:
    score = 0
    due = task.get("due_date")
    if due:
        try:
            due_d = datetime.strptime(due, "%Y-%m-%d").date()
        except ValueError:
            due_d = None
        if due_d:
            delta = (due_d - today).days
            if delta < 0:
                score += 1000
            else:
                score += max(0, 100 - delta * 10)
    if task["task_type"] == "exam_prep":
        soonest = None
        sid = task.get("subject_untis_id")
        if sid in exam_lookup:
            soonest = exam_lookup[sid]
        if soonest and (soonest - today).days <= 3:
            score += 200
    if task["task_type"] == "catch_up":
        score += 30
    return score


@router.get("/accounts/{account_id}/afternoon-plan")
def afternoon_plan(
    account_id: int,
    budget_minutes: int | None = Query(default=None, ge=0),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    today = date.today()
    if budget_minutes is not None:
        budget = budget_minutes
        budget_source = {"source": "ad_hoc_override"}
    else:
        budget, budget_source = _budget_for_today(account_id, today)

    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks "
            "WHERE account_id = ? AND status IN ('open', 'in_progress') "
            "ORDER BY (due_date IS NULL), due_date",
            (account_id,),
        ).fetchall()
        # Time already invested today: sum estimated_minutes of tasks the
        # kid completed since local midnight. Counts toward the budget so
        # the planner doesn't keep refilling free time with new suggestions
        # whenever something gets ticked off.
        completed_today_minutes = conn.execute(
            "SELECT COALESCE(SUM(estimated_minutes), 0) FROM tasks "
            "WHERE account_id = ? AND status = 'done' "
            "AND estimated_minutes IS NOT NULL "
            "AND date(completed_at) = date('now')",
            (account_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    history = history_conn()
    try:
        exams = upcoming_exams(history, account_id, days_ahead=14)
    finally:
        history.close()
    exam_lookup: dict[int, date] = {}
    for ex in exams:
        try:
            d = datetime.strptime(ex["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        sid = ex["subject_id"]
        if sid is None:
            continue
        if sid not in exam_lookup or d < exam_lookup[sid]:
            exam_lookup[sid] = d

    today_iso = today.isoformat()
    tomorrow_iso = (today + timedelta(days=1)).isoformat()
    tasks = [dict(r) for r in rows]

    # "Pflicht heute" = überfällig + heute + morgen fällig. Eine HA mit
    # Fälligkeit morgen muss heute erledigt werden — alles andere zu spät.
    must_do = []
    candidates = []
    for t in tasks:
        due = t.get("due_date")
        if due and due <= tomorrow_iso:
            must_do.append(t)
        else:
            candidates.append(t)

    must_do.sort(key=lambda t: _priority(t, today, exam_lookup), reverse=True)
    candidates.sort(key=lambda t: _priority(t, today, exam_lookup), reverse=True)

    def _est(t: dict) -> int:
        return t.get("estimated_minutes") or 20

    used = sum(_est(t) for t in must_do)
    # Already-done minutes today eat into the budget BEFORE we look for
    # suggestions, so a kid who already studied 60min doesn't keep getting
    # fresh proposals.
    suggested: list[dict] = []
    remaining = max(0, budget - used - completed_today_minutes)
    for t in candidates:
        est = _est(t)
        if est <= remaining:
            suggested.append(t)
            remaining -= est

    upcoming_exam_block = []
    for ex in exams:
        try:
            d = datetime.strptime(ex["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if (d - today).days <= 7:
            upcoming_exam_block.append(ex)

    remaining_minutes = max(
        0, budget - used - completed_today_minutes - sum(_est(t) for t in suggested)
    )
    free_learning = _free_learning_suggestions(
        account_id, user.id, today, remaining_minutes
    )

    return {
        "date": today_iso,
        "budget_minutes": budget,
        "budget_source": budget_source,
        "completed_today_minutes": completed_today_minutes,
        "must_do": must_do,
        "must_do_minutes": used,
        "suggested": suggested,
        "suggested_minutes": sum(_est(t) for t in suggested),
        "remaining_minutes": remaining_minutes,
        "free_learning": free_learning,
        "upcoming_exams_7d": upcoming_exam_block,
    }


# Subjects that don't make sense to "prepare" or learn for at home.
_NON_ACADEMIC = ("sport", "schwimm", "mittag", "pause", "förder", "klassenrat", "klassenlehrer")
# Language subjects → vocab practice makes sense.
_LANGUAGES = ("englisch", "franz", "spanisch", "latein", "italien", "russisch", "griechisch")


def _is_non_academic(name: str | None, short: str | None) -> bool:
    hay = f"{(name or '').lower()} {(short or '').lower()}"
    return any(w in hay for w in _NON_ACADEMIC)


def _language_of(name: str | None) -> str | None:
    low = (name or "").lower()
    for lang in _LANGUAGES:
        if lang in low:
            return name
    return None


def _free_learning_suggestions(
    account_id: int, user_id: int, today, remaining_minutes: int
) -> list[dict]:
    """Fill leftover study time with useful, low-pressure ideas:
    1) revisit recently hard-to-understand subjects,
    2) prep tomorrow's (real, non-cancelled, non-sport) lessons,
    3) vocab for language subjects.
    Deduplicated by subject; understanding > prep > vocab."""
    if remaining_minutes < 5:
        return []

    from ..queries import _subject_short_from_payload  # local import, avoid cycle

    horizon = (today - timedelta(days=21)).isoformat()
    tomorrow_iso = (today + timedelta(days=1)).isoformat()

    suggestions: list[dict] = []
    seen_subjects: set[str] = set()

    # 1) Recently hard (rating 1 or 2) — shared across the account.
    wconn = webapp_conn()
    try:
        hard_rows = wconn.execute(
            "SELECT lesson_id, rating, updated_at FROM lesson_checkins "
            "WHERE account_id = ? AND rating <= 2 "
            "AND updated_at >= ? ORDER BY rating ASC, updated_at DESC LIMIT 30",
            (account_id, horizon),
        ).fetchall()
    finally:
        wconn.close()

    hconn = history_conn()
    try:
        if hard_rows:
            ids = [r["lesson_id"] for r in hard_rows]
            placeholder = ",".join("?" for _ in ids)
            meta = {
                m["id"]: m
                for m in hconn.execute(
                    f"SELECT id, subject_untis_id, subject_name, payload_json "
                    f"FROM lessons WHERE id IN ({placeholder})",
                    ids,
                ).fetchall()
            }
            for r in hard_rows:
                m = meta.get(r["lesson_id"])
                if not m or not m["subject_name"]:
                    continue
                name = m["subject_name"]
                if name in seen_subjects or _is_non_academic(name, None):
                    continue
                seen_subjects.add(name)
                suggestions.append({
                    "type": "understanding",
                    "subject_id": m["subject_untis_id"],
                    "subject_name": name,
                    "subject_short": _subject_short_from_payload(m["payload_json"]),
                    "reason": "zuletzt schwer verständlich",
                    "suggested_minutes": 20,
                })
                if len(suggestions) >= 4:
                    break

        # 2) Prepare tomorrow's real lessons (skip cancelled/substituted).
        tmrw = hconn.execute(
            "SELECT subject_untis_id, subject_name, payload_json, code, "
            "is_teacher_substituted, is_subject_substituted "
            "FROM lessons WHERE account_id = ? AND date = ? "
            "AND (code IS NULL OR LOWER(code) != 'cancelled')",
            (account_id, tomorrow_iso),
        ).fetchall()
        for m in tmrw:
            name = m["subject_name"]
            if not name or name in seen_subjects:
                continue
            if (m["code"] or "").lower() == "irregular" \
                    or m["is_teacher_substituted"] or m["is_subject_substituted"]:
                continue
            if _is_non_academic(name, None):
                continue
            seen_subjects.add(name)
            suggestions.append({
                "type": "prep_tomorrow",
                "subject_id": m["subject_untis_id"],
                "subject_name": name,
                "subject_short": _subject_short_from_payload(m["payload_json"]),
                "reason": "morgen Unterricht",
                "suggested_minutes": 15,
            })

        # 3) Vocab for language subjects seen recently.
        langs = hconn.execute(
            "SELECT DISTINCT subject_untis_id, subject_name, payload_json "
            "FROM lessons WHERE account_id = ? AND date >= ? "
            "AND subject_name IS NOT NULL",
            (account_id, (today - timedelta(days=60)).isoformat()),
        ).fetchall()
        for m in langs:
            name = _language_of(m["subject_name"])
            if not name or name in seen_subjects:
                continue
            seen_subjects.add(name)
            suggestions.append({
                "type": "vocab",
                "subject_id": m["subject_untis_id"],
                "subject_name": name,
                "subject_short": _subject_short_from_payload(m["payload_json"]),
                "reason": "Vokabeln üben",
                "suggested_minutes": 15,
            })
    finally:
        hconn.close()

    # Order: understanding first, then prep, then vocab; keep it digestible.
    order = {"understanding": 0, "prep_tomorrow": 1, "vocab": 2}
    suggestions.sort(key=lambda s: order.get(s["type"], 9))
    return suggestions[:6]
