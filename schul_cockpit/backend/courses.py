"""Course (Fach + Lehrer) identity and the per-account hidden set.

WebUntis returns every parallel course of an elective band (Kursband) in a
student's timetable, even ones the kid doesn't take. The parent hides the
not-attended courses; a course is identified by subject + teacher so a kid
who takes exactly one of several parallel courses can keep that one.
"""

from __future__ import annotations

from datetime import date, timedelta

from .db import history_conn, webapp_conn


def course_key(
    subject_untis_id, teacher_untis_id, subject_name=None, teacher_name=None
) -> str:
    if subject_untis_id is not None and teacher_untis_id is not None:
        return f"{subject_untis_id}:{teacher_untis_id}"
    s = (subject_name or "").strip().lower()
    t = (teacher_name or "").strip().lower()
    return f"n:{s}|{t}"


def hidden_keys(account_id: int) -> set[str]:
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT course_key FROM hidden_courses WHERE account_id = ?",
            (account_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["course_key"] for r in rows}


def lesson_is_hidden(lesson: dict, hidden: set[str]) -> bool:
    """lesson dict must carry subject_untis_id, teacher_untis_id, and
    subject_name/teacher_name for the name fallback."""
    if not hidden:
        return False
    return course_key(
        lesson.get("subject_untis_id"),
        lesson.get("teacher_untis_id"),
        lesson.get("subject_name"),
        lesson.get("teacher_name"),
    ) in hidden


def visible_subject_ids(account_id: int, *, days_back: int = 365) -> set | None:
    """Subject ids that still have at least one NON-hidden course. Returns
    None when nothing is hidden (caller can skip filtering entirely)."""
    hidden = hidden_keys(account_id)
    if not hidden:
        return None
    horizon = (date.today() - timedelta(days=days_back)).isoformat()
    hconn = history_conn()
    try:
        rows = hconn.execute(
            "SELECT DISTINCT subject_untis_id, teacher_untis_id, subject_name, teacher_name "
            "FROM lessons WHERE account_id = ? AND subject_untis_id IS NOT NULL "
            "AND date >= ?",
            (account_id, horizon),
        ).fetchall()
    finally:
        hconn.close()
    visible: set = set()
    for r in rows:
        key = course_key(r["subject_untis_id"], r["teacher_untis_id"],
                         r["subject_name"], r["teacher_name"])
        if key not in hidden:
            visible.add(r["subject_untis_id"])
    return visible


def list_courses(account_id: int, *, days_back: int = 120) -> list[dict]:
    """Distinct (subject, teacher) courses in the kid's recent timetable,
    with occurrence count and hidden flag."""
    horizon = (date.today() - timedelta(days=days_back)).isoformat()
    ahead = (date.today() + timedelta(days=14)).isoformat()
    hconn = history_conn()
    try:
        rows = hconn.execute(
            "SELECT subject_untis_id, subject_name, teacher_untis_id, teacher_name, "
            "COUNT(*) AS cnt "
            "FROM lessons WHERE account_id = ? AND subject_name IS NOT NULL "
            "AND date >= ? AND date <= ? "
            "AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "GROUP BY subject_untis_id, subject_name, teacher_untis_id, teacher_name "
            "ORDER BY subject_name, teacher_name",
            (account_id, horizon, ahead),
        ).fetchall()
    finally:
        hconn.close()
    hidden = hidden_keys(account_id)
    out = []
    for r in rows:
        key = course_key(
            r["subject_untis_id"], r["teacher_untis_id"],
            r["subject_name"], r["teacher_name"],
        )
        out.append({
            "course_key": key,
            "subject_untis_id": r["subject_untis_id"],
            "subject_name": r["subject_name"],
            "teacher_untis_id": r["teacher_untis_id"],
            "teacher_name": r["teacher_name"],
            "count": r["cnt"],
            "hidden": key in hidden,
        })
    return out
