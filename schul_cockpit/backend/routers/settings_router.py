from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..audit import log as audit_log, snapshot_settings
from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import webapp_conn

router = APIRouter()

WEEKDAY_KEYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


class SettingsIn(BaseModel):
    default_daily_budget_minutes: int | None = Field(default=None, ge=0)
    budget_overrides: dict[str, int] | None = None


@router.get("/accounts/{account_id}/settings")
def get_settings(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
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
        return {
            "default_daily_budget_minutes": 60,
            "budget_overrides": {},
        }
    overrides = {}
    if row["budget_overrides_json"]:
        try:
            overrides = json.loads(row["budget_overrides_json"])
        except json.JSONDecodeError:
            overrides = {}
    return {
        "default_daily_budget_minutes": row["default_daily_budget_minutes"],
        "budget_overrides": overrides,
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
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (
                    account_id,
                    body.default_daily_budget_minutes or 60,
                    json.dumps(body.budget_overrides or {}),
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
