"""Manage which courses (Fach + Lehrer) the kid actually attends.

Hidden courses disappear from Heute, Woche, Fächer, oral suggestions and
exam subject detection — fixes the WebUntis Kursband returning every
parallel elective (Instrumental/Gesang …) in a student's timetable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..courses import course_key, list_courses
from ..db import history_conn, webapp_conn

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_parent(user: CurrentUser) -> None:
    if not (user.is_admin or user.role == "parent"):
        raise HTTPException(status_code=403, detail="Admin or parent only")


@router.get("/accounts/{account_id}/courses")
def get_courses(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    return {"courses": list_courses(account_id)}


class HideCourseIn(BaseModel):
    course_key: str
    subject_untis_id: int | None = None
    subject_name: str | None = None
    teacher_untis_id: int | None = None
    teacher_name: str | None = None
    hidden: bool


@router.post("/accounts/{account_id}/courses/hidden")
def set_course_hidden(
    account_id: int,
    body: HideCourseIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    conn = webapp_conn()
    try:
        if body.hidden:
            conn.execute(
                "INSERT INTO hidden_courses "
                "(account_id, course_key, subject_untis_id, subject_name, "
                " teacher_untis_id, teacher_name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(account_id, course_key) DO NOTHING",
                (account_id, body.course_key, body.subject_untis_id, body.subject_name,
                 body.teacher_untis_id, body.teacher_name, _now()),
            )
        else:
            conn.execute(
                "DELETE FROM hidden_courses WHERE account_id = ? AND course_key = ?",
                (account_id, body.course_key),
            )
    finally:
        conn.close()
    return {"ok": True}


class HideSubjectIn(BaseModel):
    subject_untis_id: int | None = None
    subject_name: str | None = None
    hidden: bool


@router.post("/accounts/{account_id}/courses/hide-subject")
def hide_whole_subject(
    account_id: int,
    body: HideSubjectIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Hide/show every course of a subject in one tap."""
    assert_account_access(user, account_id)
    _require_parent(user)
    # Gather all (teacher) courses of this subject from history.
    hconn = history_conn()
    try:
        if body.subject_untis_id is not None:
            rows = hconn.execute(
                "SELECT DISTINCT subject_untis_id, subject_name, teacher_untis_id, teacher_name "
                "FROM lessons WHERE account_id = ? AND subject_untis_id = ?",
                (account_id, body.subject_untis_id),
            ).fetchall()
        else:
            rows = hconn.execute(
                "SELECT DISTINCT subject_untis_id, subject_name, teacher_untis_id, teacher_name "
                "FROM lessons WHERE account_id = ? AND subject_name = ?",
                (account_id, body.subject_name),
            ).fetchall()
    finally:
        hconn.close()

    conn = webapp_conn()
    try:
        for r in rows:
            key = course_key(r["subject_untis_id"], r["teacher_untis_id"],
                             r["subject_name"], r["teacher_name"])
            if body.hidden:
                conn.execute(
                    "INSERT INTO hidden_courses "
                    "(account_id, course_key, subject_untis_id, subject_name, "
                    " teacher_untis_id, teacher_name, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(account_id, course_key) DO NOTHING",
                    (account_id, key, r["subject_untis_id"], r["subject_name"],
                     r["teacher_untis_id"], r["teacher_name"], _now()),
                )
            else:
                conn.execute(
                    "DELETE FROM hidden_courses WHERE account_id = ? AND course_key = ?",
                    (account_id, key),
                )
    finally:
        conn.close()
    return {"ok": True}
