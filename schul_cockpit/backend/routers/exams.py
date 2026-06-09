"""Exam calendar linking, subject overrides, manual exams, diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import CurrentUser, assert_account_access, get_current_user, require_admin
from ..db import webapp_conn
from ..exams import (
    DEFAULT_EXCLUDE_KEYWORDS,
    account_subjects,
    resolve_exams,
)
from ..supervisor_client import SupervisorError, get_supervisor

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_parent(user: CurrentUser) -> None:
    if not (user.is_admin or user.role == "parent"):
        raise HTTPException(status_code=403, detail="Admin or parent only")


# ---- App-facing: relevant exams -----------------------------------------

@router.get("/accounts/{account_id}/exams")
async def get_exams(
    account_id: int,
    days_ahead: int = 90,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    return await resolve_exams(account_id, days_ahead=days_ahead)


# ---- Diagnostic + curation (parent) -------------------------------------

@router.get("/accounts/{account_id}/exams/diagnostic")
async def exams_diagnostic(
    account_id: int,
    days_ahead: int = 90,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    data = await resolve_exams(account_id, days_ahead=days_ahead, diagnostic=True)
    data["subjects"] = account_subjects(account_id)
    return data


@router.get("/accounts/{account_id}/calendar-entities")
async def calendar_entities(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    sup = get_supervisor()
    if not sup.available:
        return {"available": False, "entities": []}
    try:
        ents = await sup.list_calendar_entities()
    except SupervisorError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {
        "available": True,
        "entities": [
            {"entity_id": e["entity_id"],
             "friendly_name": (e.get("attributes") or {}).get("friendly_name")}
            for e in ents
        ],
    }


class CalendarConfigIn(BaseModel):
    ha_entity_id: str
    exclude_keywords: list[str] | None = None


@router.get("/accounts/{account_id}/exam-calendar")
def get_exam_calendar(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT ha_entity_id, exclude_keywords FROM account_exam_calendars "
            "WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"ha_entity_id": None, "exclude_keywords": DEFAULT_EXCLUDE_KEYWORDS}
    kws = (row["exclude_keywords"] or "")
    return {
        "ha_entity_id": row["ha_entity_id"],
        "exclude_keywords": [k.strip() for k in kws.split(",") if k.strip()]
        or DEFAULT_EXCLUDE_KEYWORDS,
    }


@router.put("/accounts/{account_id}/exam-calendar")
def set_exam_calendar(
    account_id: int,
    body: CalendarConfigIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    kws = ",".join(k.strip() for k in (body.exclude_keywords or DEFAULT_EXCLUDE_KEYWORDS) if k.strip())
    conn = webapp_conn()
    try:
        conn.execute(
            "INSERT INTO account_exam_calendars (account_id, ha_entity_id, exclude_keywords, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(account_id) DO UPDATE SET "
            "  ha_entity_id = excluded.ha_entity_id, "
            "  exclude_keywords = excluded.exclude_keywords, "
            "  updated_at = excluded.updated_at",
            (account_id, body.ha_entity_id, kws, _now()),
        )
    finally:
        conn.close()
    return {"ok": True}


class OverrideIn(BaseModel):
    source_key: str
    decision: str  # 'assigned' | 'dismissed' | 'reset'
    subject_name: str | None = None
    subject_untis_id: int | None = None


@router.post("/accounts/{account_id}/exam-overrides")
def set_override(
    account_id: int,
    body: OverrideIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    conn = webapp_conn()
    try:
        if body.decision == "reset":
            conn.execute(
                "DELETE FROM exam_overrides WHERE account_id = ? AND source_key = ?",
                (account_id, body.source_key),
            )
            return {"ok": True}
        if body.decision == "assigned" and not body.subject_name:
            raise HTTPException(status_code=400, detail="subject_name required when assigning")
        if body.decision not in ("assigned", "dismissed"):
            raise HTTPException(status_code=400, detail="invalid decision")
        conn.execute(
            "INSERT INTO exam_overrides "
            "(account_id, source_key, decision, subject_name, subject_untis_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, source_key) DO UPDATE SET "
            "  decision = excluded.decision, subject_name = excluded.subject_name, "
            "  subject_untis_id = excluded.subject_untis_id, updated_at = excluded.updated_at",
            (account_id, body.source_key, body.decision, body.subject_name,
             body.subject_untis_id, _now()),
        )
    finally:
        conn.close()
    return {"ok": True}


class ManualExamIn(BaseModel):
    exam_date: str  # YYYY-MM-DD
    subject_name: str
    subject_untis_id: int | None = None
    title: str | None = None
    note: str | None = None


@router.post("/accounts/{account_id}/manual-exams", status_code=201)
def add_manual_exam(
    account_id: int,
    body: ManualExamIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    conn = webapp_conn()
    try:
        cur = conn.execute(
            "INSERT INTO manual_exams "
            "(account_id, exam_date, subject_name, subject_untis_id, title, note, "
            " created_by_user_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, body.exam_date, body.subject_name, body.subject_untis_id,
             body.title, body.note, user.id, _now()),
        )
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@router.delete("/accounts/{account_id}/manual-exams/{exam_id}")
def delete_manual_exam(
    account_id: int,
    exam_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    conn = webapp_conn()
    try:
        conn.execute(
            "DELETE FROM manual_exams WHERE account_id = ? AND id = ?",
            (account_id, exam_id),
        )
    finally:
        conn.close()
    return {"ok": True}
