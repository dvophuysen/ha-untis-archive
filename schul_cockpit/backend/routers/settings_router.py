from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..audit import log as audit_log, snapshot_settings
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import webapp_conn
from ..erlass import (
    ERLASS_DAILY_MIN,
    WEEKEND_MIN,
    AFTERNOON_REDUCTION_FACTOR,
    has_afternoon_school,
    resolve_section,
)
from datetime import date as _date

router = APIRouter()

WEEKDAY_KEYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_SECTIONS = {"primar", "sek1", "sek2"}


class SettingsIn(BaseModel):
    default_daily_budget_minutes: int | None = Field(default=None, ge=0)
    budget_overrides: dict[str, int] | None = None
    auto_budget: bool | None = None
    school_section_override: str | None = None  # 'primar' | 'sek1' | 'sek2' | '' to clear


@router.get("/accounts/{account_id}/settings")
def get_settings(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
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

    overrides = {}
    if row and row["budget_overrides_json"]:
        try:
            overrides = json.loads(row["budget_overrides_json"])
        except json.JSONDecodeError:
            overrides = {}

    auto_budget = True if row is None else bool(row["auto_budget"])
    section_override = row["school_section_override"] if row else None
    section, klasse_name, section_source = resolve_section(account_id, section_override)
    today = _date.today()
    afternoon = has_afternoon_school(account_id, today)

    erlass = {
        "section": section,
        "section_source": section_source,
        "klasse_name": klasse_name,
        "max_workday_minutes": ERLASS_DAILY_MIN.get(section, None) if section else None,
        "weekend_minutes": WEEKEND_MIN,
        "afternoon_reduction_factor": AFTERNOON_REDUCTION_FACTOR,
        "has_afternoon_today": afternoon,
    }

    return {
        "default_daily_budget_minutes": (row and row["default_daily_budget_minutes"]) or 60,
        "budget_overrides": overrides,
        "auto_budget": auto_budget,
        "school_section_override": section_override,
        "erlass": erlass,
    }


@router.patch("/accounts/{account_id}/settings")
def patch_settings(
    account_id: int,
    body: SettingsIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    if body.budget_overrides is not None:
        invalid = set(body.budget_overrides) - WEEKDAY_KEYS
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"invalid weekday keys: {sorted(invalid)} (allowed: {sorted(WEEKDAY_KEYS)})",
            )
    if (
        body.school_section_override is not None
        and body.school_section_override != ""
        and body.school_section_override not in VALID_SECTIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=f"invalid school_section_override (allowed: {sorted(VALID_SECTIONS)})",
        )

    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        before = snapshot_settings(conn, account_id)
        existing = conn.execute(
            "SELECT 1 FROM account_settings WHERE account_id = ?", (account_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO account_settings "
                "(account_id, default_daily_budget_minutes, budget_overrides_json, "
                " auto_budget, school_section_override, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id,
                    body.default_daily_budget_minutes or 60,
                    json.dumps(body.budget_overrides or {}),
                    1 if (body.auto_budget if body.auto_budget is not None else True) else 0,
                    body.school_section_override or None,
                    now,
                    now,
                ),
            )
        else:
            fields = []
            params: list = []
            if body.default_daily_budget_minutes is not None:
                fields.append("default_daily_budget_minutes = ?")
                params.append(body.default_daily_budget_minutes)
            if body.budget_overrides is not None:
                fields.append("budget_overrides_json = ?")
                params.append(json.dumps(body.budget_overrides))
            if body.auto_budget is not None:
                fields.append("auto_budget = ?")
                params.append(1 if body.auto_budget else 0)
            if body.school_section_override is not None:
                fields.append("school_section_override = ?")
                params.append(body.school_section_override or None)
            if fields:
                fields.append("updated_at = ?")
                params.append(now)
                params.append(account_id)
                conn.execute(
                    f"UPDATE account_settings SET {', '.join(fields)} WHERE account_id = ?",
                    params,
                )
        after = snapshot_settings(conn, account_id)
        audit_log(
            conn,
            user_id=user.id,
            account_id=account_id,
            op_type="insert" if before is None else "update",
            target_kind="settings",
            target_id=account_id,
            label="Lernzeit-Einstellungen geändert",
            before=before,
            after=after,
        )
    finally:
        conn.close()
    return {"ok": True}
