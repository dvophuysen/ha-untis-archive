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
    data = await resolve_exams(account_id, days_ahead=days_ahead)
    # Lernstand mitschicken — der Header und der Plan zeigen das Emoji,
    # damit der Vorbereitungs-Stand überall präsent ist und nicht nur auf
    # der Klausuren-Seite.
    prog = _progress_map(account_id)
    data["exams"] = [
        {**e, "learn_state": prog.get(e.get("exam_key"), {}).get("learn_state")}
        for e in data.get("exams", [])
    ]
    return data


def _progress_map(account_id: int) -> dict:
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT exam_key, learn_state, learn_note, grade_points FROM exam_progress "
            "WHERE account_id = ?",
            (account_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["exam_key"]: dict(r) for r in rows}


@router.get("/accounts/{account_id}/exams/all")
async def exams_all(
    account_id: int,
    past_days: int = 365,
    days_ahead: int = 180,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Dedicated exam page feed: upcoming (soonest first) + past (most
    recent first), each merged with learn-state / grade progress."""
    assert_account_access(user, account_id)
    data = await resolve_exams(account_id, days_ahead=days_ahead, past_days=past_days)
    prog = _progress_map(account_id)
    from datetime import date as _d

    from ..erlass import resolve_section
    from ..grades import display_label, options as grade_options

    today_iso = _d.today().isoformat()
    section, _kl, _src = resolve_section(account_id)

    upcoming, past = [], []
    for e in data["exams"]:
        p = prog.get(e.get("exam_key"), {})
        gp = p.get("grade_points")
        e = {
            **e,
            "learn_state": p.get("learn_state"),
            "learn_note": p.get("learn_note"),
            "grade_points": gp,
            "grade_label": display_label(gp, section),
        }
        (upcoming if e["date"] >= today_iso else past).append(e)

    upcoming.sort(key=lambda e: e["date"])              # soonest first
    past.sort(key=lambda e: e["date"], reverse=True)    # most recent first
    return {
        "calendar_error": data.get("calendar_error"),
        "entity_id": data.get("entity_id"),
        "section": section,
        "grade_options": grade_options(section),
        "upcoming": upcoming,
        "past": past,
    }


class ProgressIn(BaseModel):
    exam_key: str
    learn_state: int | None = Field(default=None, ge=0, le=3)
    learn_note: str | None = None
    grade_points: int | None = Field(default=None, ge=0, le=15)
    # Sentinel to explicitly clear the grade (since None = "leave as-is").
    clear_grade: bool = False


@router.post("/accounts/{account_id}/exam-progress")
def set_progress(
    account_id: int,
    body: ProgressIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    # Any linked user (kid for self-assessment, parent for grade) may set it.
    assert_account_access(user, account_id)
    now = _now()
    conn = webapp_conn()
    try:
        existing = conn.execute(
            "SELECT learn_state, learn_note, grade_points FROM exam_progress "
            "WHERE account_id = ? AND exam_key = ?",
            (account_id, body.exam_key),
        ).fetchone()
        # Merge: only overwrite fields that were provided (None = leave as-is).
        learn_state = body.learn_state if body.learn_state is not None else (existing["learn_state"] if existing else None)
        learn_note = body.learn_note if body.learn_note is not None else (existing["learn_note"] if existing else None)
        if body.clear_grade:
            grade_points = None
        elif body.grade_points is not None:
            grade_points = body.grade_points
        else:
            grade_points = existing["grade_points"] if existing else None
        conn.execute(
            "INSERT INTO exam_progress (account_id, exam_key, learn_state, learn_note, grade_points, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, exam_key) DO UPDATE SET "
            "  learn_state = excluded.learn_state, learn_note = excluded.learn_note, "
            "  grade_points = excluded.grade_points, updated_at = excluded.updated_at",
            (account_id, body.exam_key, learn_state, learn_note, grade_points, now),
        )
    finally:
        conn.close()
    return {"ok": True}


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
