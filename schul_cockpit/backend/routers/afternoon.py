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
            default = row["default_daily_budget_minutes"] if row else 60
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
    default = row["default_daily_budget_minutes"] if row else 60
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
async def afternoon_plan(account_id:int,budget_minutes:int|None=Query(default=None,ge=0),user:CurrentUser=Depends(get_current_user)):
    assert_account_access(user,account_id)
    from .. import learning_plan as lp
    from .plan import plan as shared_plan
    plan=await shared_plan(account_id,user)
    if budget_minutes is not None:plan=lp.build(account_id,plan['upcoming_exams'],budget_override=budget_minutes)
    t=plan['today']
    return dict(date=plan['date'],budget_minutes=t['budget_minutes'],budget_source=t['budget_source'],completed_today_minutes=t['used_minutes'],must_do=t['homework'],must_do_minutes=t['homework_minutes'],suggested=[],suggested_minutes=0,remaining_minutes=t['remaining_minutes'],free_learning=[dict(type=g['kind'],subject_id=g.get('subject_id'),subject_name=g['subject'],reason=g['reason'],suggested_minutes=g['minutes'],goal_key=g['key'],url=g['url']) for g in t['actions']],upcoming_exams_7d=[],shared_plan=plan)
