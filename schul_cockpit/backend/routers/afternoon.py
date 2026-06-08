"""Afternoon planner: prioritized list of tasks fitting into today's time budget."""

from __future__ import annotations

import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..queries import upcoming_exams

router = APIRouter()

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _budget_for_today(account_id: int, today: date) -> int:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT default_daily_budget_minutes, budget_overrides_json "
            "FROM account_settings WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return 60
    default = row["default_daily_budget_minutes"] or 60
    overrides_raw = row["budget_overrides_json"]
    if not overrides_raw:
        return default
    try:
        overrides = json.loads(overrides_raw)
    except json.JSONDecodeError:
        return default
    key = WEEKDAY_KEYS[today.weekday()]
    val = overrides.get(key)
    if val is None:
        return default
    return int(val)


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
    budget = budget_minutes if budget_minutes is not None else _budget_for_today(account_id, today)

    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks "
            "WHERE account_id = ? AND status IN ('open', 'in_progress') "
            "ORDER BY (due_date IS NULL), due_date",
            (account_id,),
        ).fetchall()
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
    tasks = [dict(r) for r in rows]

    must_do = []
    candidates = []
    for t in tasks:
        due = t.get("due_date")
        if due and due <= today_iso:
            must_do.append(t)
        else:
            candidates.append(t)

    must_do.sort(key=lambda t: _priority(t, today, exam_lookup), reverse=True)
    candidates.sort(key=lambda t: _priority(t, today, exam_lookup), reverse=True)

    def _est(t: dict) -> int:
        return t.get("estimated_minutes") or 20

    used = sum(_est(t) for t in must_do)
    suggested: list[dict] = []
    remaining = max(0, budget - used)
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

    return {
        "date": today_iso,
        "budget_minutes": budget,
        "must_do": must_do,
        "must_do_minutes": used,
        "suggested": suggested,
        "suggested_minutes": sum(_est(t) for t in suggested),
        "remaining_minutes": max(0, budget - used - sum(_est(t) for t in suggested)),
        "upcoming_exams_7d": upcoming_exam_block,
    }
