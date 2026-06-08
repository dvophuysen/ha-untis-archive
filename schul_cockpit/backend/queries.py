"""Reusable read-only queries against history.db."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def lessons_for_date(
    conn: sqlite3.Connection, account_id: int, date_iso: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, untis_period_id, date, start_time, end_time, "
        "subject_untis_id, subject_name, teacher_name, teacher_orig_name, "
        "room, room_orig, subject_orig_name, "
        "is_teacher_substituted, is_room_substituted, is_subject_substituted, "
        "code, lstext, subst_text, info, was_absent, absence_reason, "
        "is_late_addition, period_info_json, payload_json "
        "FROM lessons WHERE account_id = ? AND date = ? "
        "ORDER BY start_time, end_time",
        (account_id, date_iso),
    ).fetchall()
    return [_lesson_row(r) for r in rows]


def lessons_in_range(
    conn: sqlite3.Connection,
    account_id: int,
    date_from_iso: str,
    date_to_iso: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, untis_period_id, date, start_time, end_time, "
        "subject_untis_id, subject_name, teacher_name, teacher_orig_name, "
        "room, room_orig, subject_orig_name, "
        "is_teacher_substituted, is_room_substituted, is_subject_substituted, "
        "code, lstext, subst_text, info, was_absent, absence_reason, "
        "is_late_addition, period_info_json, payload_json "
        "FROM lessons WHERE account_id = ? AND date BETWEEN ? AND ? "
        "ORDER BY date, start_time",
        (account_id, date_from_iso, date_to_iso),
    ).fetchall()
    return [_lesson_row(r) for r in rows]


def _subject_short_from_payload(payload_json: str | None) -> str | None:
    """The real Untis subject Kürzel (su[0].name), not the long name."""
    if not payload_json:
        return None
    try:
        parsed = json.loads(payload_json)
    except (json.JSONDecodeError, TypeError):
        return None
    su = parsed.get("su")
    if isinstance(su, list) and su and isinstance(su[0], dict):
        return su[0].get("name") or None
    return None


def _lesson_row(r: sqlite3.Row) -> dict[str, Any]:
    info = dict(r)
    pj = info.pop("period_info_json", None)
    payload = info.pop("payload_json", None)
    info["subject_short"] = _subject_short_from_payload(payload)
    info["exam"] = None
    info["lesson_topic"] = None
    if pj:
        try:
            parsed = json.loads(pj)
            exam = parsed.get("exam")
            if exam:
                info["exam"] = {
                    "name": exam.get("name"),
                    "text": exam.get("text"),
                    "id": exam.get("id"),
                }
            topic = parsed.get("lessonTopic") or parsed.get("lessontopic")
            if topic and isinstance(topic, dict):
                info["lesson_topic"] = topic.get("text")
        except json.JSONDecodeError:
            pass
    info["start_hhmm"] = _fmt_hhmm(info["start_time"])
    info["end_hhmm"] = _fmt_hhmm(info["end_time"])
    info["is_cancelled"] = (info.get("code") or "").lower() == "cancelled"
    info["is_irregular"] = (info.get("code") or "").lower() == "irregular"
    return info


def _fmt_hhmm(value: int | None) -> str | None:
    if value is None:
        return None
    s = f"{value:04d}"
    return f"{s[:2]}:{s[2:]}"


def subjects_for_account(
    conn: sqlite3.Connection, account_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT subject_untis_id, subject_name, COUNT(*) AS lesson_count "
        "FROM lessons WHERE account_id = ? AND subject_untis_id IS NOT NULL "
        "GROUP BY subject_untis_id, subject_name "
        "ORDER BY subject_name",
        (account_id,),
    ).fetchall()
    return [
        {
            "subject_id": r["subject_untis_id"],
            "name": r["subject_name"],
            "lesson_count": r["lesson_count"],
        }
        for r in rows
    ]


def absences_for_account(
    conn: sqlite3.Connection, account_id: int, *, days_back: int = 400
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, start_date, end_date, reason, is_excused "
        "FROM absences WHERE account_id = ? "
        "ORDER BY start_date DESC LIMIT 200",
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def upcoming_exams(
    conn: sqlite3.Connection, account_id: int, *, days_ahead: int = 21
) -> list[dict[str, Any]]:
    """Lessons in the next N days whose period_info_json contains an exam."""
    rows = conn.execute(
        "SELECT id, date, start_time, subject_untis_id, subject_name, "
        "period_info_json FROM lessons "
        "WHERE account_id = ? AND date >= date('now') "
        "AND date <= date('now', ?) "
        "AND period_info_json IS NOT NULL "
        "ORDER BY date, start_time",
        (account_id, f"+{days_ahead} days"),
    ).fetchall()
    exams = []
    for r in rows:
        try:
            parsed = json.loads(r["period_info_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        exam = parsed.get("exam")
        if not exam:
            continue
        exams.append(
            {
                "lesson_id": r["id"],
                "date": r["date"],
                "start_hhmm": _fmt_hhmm(r["start_time"]),
                "subject_id": r["subject_untis_id"],
                "subject_name": r["subject_name"],
                "name": exam.get("name"),
                "text": exam.get("text"),
            }
        )
    return exams
