"""Lightweight, token-authenticated data feed for HA automations.

Designed for the user's existing setup: HA cron + Hermes/WhatsApp.
HA fires a GET against /api/notify/<account_id>/summary?token=<secret>,
gets a compact JSON with live numbers and ready-to-paste deep links to
the right app subpage, and weaves it into a message.

No subscriptions, no VAPID, no service worker — your push pipeline.
"""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import CurrentUser, get_current_user, require_admin
from ..config import SETTINGS
from ..db import history_conn, webapp_conn
from ..queries import upcoming_exams

router = APIRouter()


# ---- Token management (admin/parent endpoints) ---------------------------

def _get_or_create_token(account_id: int) -> str:
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT notify_token FROM account_settings WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        token = (row and row["notify_token"]) or None
        if token:
            return token
        token = secrets.token_urlsafe(24)
        # Upsert: either an existing settings row gets the token, or we
        # create one with sensible defaults.
        if row is None:
            conn.execute(
                "INSERT INTO account_settings "
                "(account_id, default_daily_budget_minutes, notify_token, "
                " created_at, updated_at) "
                "VALUES (?, 60, ?, ?, ?)",
                (account_id, token, now, now),
            )
        else:
            conn.execute(
                "UPDATE account_settings SET notify_token = ?, updated_at = ? "
                "WHERE account_id = ?",
                (token, now, account_id),
            )
        return token
    finally:
        conn.close()


def _require_admin_or_parent(user: CurrentUser) -> None:
    if not (user.is_admin or user.role == "parent"):
        raise HTTPException(status_code=403, detail="Admin or parent only")


@router.get("/accounts/{account_id}/notify-token")
def show_notify_token(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    _require_admin_or_parent(user)
    return {"token": _get_or_create_token(account_id)}


@router.post("/accounts/{account_id}/notify-token/rotate")
def rotate_notify_token(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    require_admin(user)
    new_token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc).isoformat()
    conn = webapp_conn()
    try:
        # Make sure the settings row exists before rotating.
        exists = conn.execute(
            "SELECT 1 FROM account_settings WHERE account_id = ?", (account_id,)
        ).fetchone()
        if exists is None:
            conn.execute(
                "INSERT INTO account_settings "
                "(account_id, default_daily_budget_minutes, notify_token, "
                " created_at, updated_at) "
                "VALUES (?, 60, ?, ?, ?)",
                (account_id, new_token, now, now),
            )
        else:
            conn.execute(
                "UPDATE account_settings SET notify_token = ?, updated_at = ? "
                "WHERE account_id = ?",
                (new_token, now, account_id),
            )
    finally:
        conn.close()
    return {"token": new_token}


# ---- Public, token-protected summary endpoint ---------------------------

def _now_hhmm() -> int:
    n = datetime.now()
    return n.hour * 100 + n.minute


def _deep_link(path: str, account_id: int) -> str:
    """Build a full URL when external_url is configured, else a relative
    one. `acc` query selects the active child after login."""
    base = SETTINGS.external_url
    rel = f"/?acc={account_id}#/{path.lstrip('/')}"
    return f"{base}{rel}" if base else rel


@router.get("/notify/{account_id}/summary")
def notify_summary(
    account_id: int,
    token: str = Query(..., description="Per-account notify_token"),
) -> dict:
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT notify_token FROM account_settings WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row["notify_token"] or row["notify_token"] != token:
        # Don't leak whether the account exists.
        raise HTTPException(status_code=401, detail="invalid token")

    today = date.today()
    today_iso = today.isoformat()
    tomorrow_iso = (today + timedelta(days=1)).isoformat()
    now_hhmm = _now_hhmm()

    # Account display name from history.db.
    hconn = history_conn()
    try:
        account = hconn.execute(
            "SELECT name FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="account not found")
        account_name = account["name"]
        lessons_today = hconn.execute(
            "SELECT id, start_time, end_time, was_absent, code FROM lessons "
            "WHERE account_id = ? AND date = ?",
            (account_id, today_iso),
        ).fetchall()
        # Subjects with their NEXT (still upcoming) lesson within ~7 days,
        # used to phrase 'pack for tomorrow' style hints.
        upcoming_subjects = [
            r["subject_name"]
            for r in hconn.execute(
                "SELECT DISTINCT subject_name FROM lessons "
                "WHERE account_id = ? AND date = ? "
                "AND (code IS NULL OR LOWER(code) != 'cancelled') "
                "AND subject_name IS NOT NULL",
                (account_id, tomorrow_iso),
            ).fetchall()
            if r["subject_name"]
        ]
        exams = upcoming_exams(hconn, account_id, days_ahead=14)
    finally:
        hconn.close()

    # Real lessons today the kid attended and that have already ended —
    # those are the ones a check-in reminder applies to.
    real_lessons_today = [
        l for l in lessons_today
        if (l["code"] or "").lower() != "cancelled" and not l["was_absent"]
    ]
    real_lesson_ids = [l["id"] for l in real_lessons_today]
    already_ended_ids = [
        l["id"] for l in real_lessons_today if (l["end_time"] or 0) <= now_hhmm
    ]

    wconn = webapp_conn()
    try:
        # Users linked to this account (typically the kid + the parents).
        linked_users = [
            r["user_id"]
            for r in wconn.execute(
                "SELECT user_id FROM user_account_links WHERE account_id = ?",
                (account_id,),
            ).fetchall()
        ]

        users_summary = []
        if linked_users and real_lesson_ids:
            lid_placeholder = ",".join("?" for _ in real_lesson_ids)
            # Check-ins gehören dem Account, nicht der einzelnen Person —
            # einmal abfragen, derselbe „unrated"-Stand gilt für alle
            # verlinkten User. Wir lassen die User-Liste in der Antwort,
            # damit bestehende HA-Automationen nicht brechen.
            rated_ids = {
                r["lesson_id"]
                for r in wconn.execute(
                    f"SELECT lesson_id FROM lesson_checkins "
                    f"WHERE account_id = ? AND lesson_id IN ({lid_placeholder})",
                    [account_id, *real_lesson_ids],
                ).fetchall()
            }
            unrated_ended = sum(1 for lid in already_ended_ids if lid not in rated_ids)
            for uid in linked_users:
                u = wconn.execute(
                    "SELECT id, display_name, role FROM users WHERE id = ?",
                    (uid,),
                ).fetchone()
                if not u:
                    continue
                users_summary.append(
                    {
                        "user_id": uid,
                        "display_name": u["display_name"],
                        "role": u["role"],
                        "unrated_lessons_today": unrated_ended,
                    }
                )

        # Tasks (per account, not per user).
        task_rows = wconn.execute(
            "SELECT due_date, status FROM tasks "
            "WHERE account_id = ? AND status IN ('open', 'in_progress')",
            (account_id,),
        ).fetchall()
        overdue = sum(1 for t in task_rows if t["due_date"] and t["due_date"] < today_iso)
        due_today = sum(1 for t in task_rows if t["due_date"] == today_iso)
        due_tomorrow = sum(1 for t in task_rows if t["due_date"] == tomorrow_iso)
        open_total = len(task_rows)

    finally:
        wconn.close()

    # Absences still open across all users — count missed real lessons in
    # the last 120 days that have no caught_up row.
    hconn = history_conn()
    try:
        absent_rows = hconn.execute(
            "SELECT id FROM lessons WHERE account_id = ? AND was_absent = 1 "
            "AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "AND date >= date('now', '-120 days') AND date <= date('now')",
            (account_id,),
        ).fetchall()
    finally:
        hconn.close()
    absent_ids = [r["id"] for r in absent_rows]

    wconn = webapp_conn()
    try:
        caught_ids: set[int] = set()
        if absent_ids:
            placeholder = ",".join("?" for _ in absent_ids)
            caught_ids = {
                r["lesson_id"]
                for r in wconn.execute(
                    f"SELECT DISTINCT lesson_id FROM caught_up "
                    f"WHERE account_id = ? AND lesson_id IN ({placeholder})",
                    [account_id, *absent_ids],
                ).fetchall()
            }
    finally:
        wconn.close()
    absent_open = len(absent_ids) - len(caught_ids)

    next_exam = None
    if exams:
        first = exams[0]
        try:
            d = datetime.strptime(first["date"], "%Y-%m-%d").date()
            days_until = (d - today).days
        except (ValueError, TypeError):
            days_until = None
        next_exam = {
            "subject": first["subject_name"],
            "date": first["date"],
            "name": first.get("name"),
            "days_until": days_until,
        }

    links = {
        "today": _deep_link("today", account_id),
        "plan": _deep_link("plan", account_id),
        "tasks": _deep_link("tasks", account_id),
        "week": _deep_link("week", account_id),
        "absences": _deep_link("absences", account_id),
        "subjects": _deep_link("subjects", account_id),
    }

    # Pre-baked German message templates, easy to plug into a HA notify
    # call. Use the ones that fit your trigger; replace or skip in HA if
    # the count is 0.
    suggested_messages = _make_messages(
        account_name=account_name,
        users_summary=users_summary,
        overdue=overdue,
        due_today=due_today,
        due_tomorrow=due_tomorrow,
        absent_open=absent_open,
        upcoming_subjects=upcoming_subjects,
        next_exam=next_exam,
        links=links,
    )

    return {
        "account": {"id": account_id, "name": account_name},
        "today": today_iso,
        "now": datetime.now().astimezone().isoformat(),
        "users": users_summary,
        "tasks": {
            "open_total": open_total,
            "overdue": overdue,
            "due_today": due_today,
            "due_tomorrow": due_tomorrow,
        },
        "absences": {
            "missed_lessons_total_120d": len(absent_ids),
            "open_to_catch_up": absent_open,
        },
        "next_exam": next_exam,
        "links": links,
        "suggested_messages": suggested_messages,
    }


def _make_messages(
    *,
    account_name: str,
    users_summary: list,
    overdue: int,
    due_today: int,
    due_tomorrow: int,
    absent_open: int,
    upcoming_subjects: list,
    next_exam: dict | None,
    links: dict,
) -> dict[str, str]:
    out: dict[str, str] = {}

    # Sum unrated across linked users (good for a single notification line).
    unrated_total = sum(u.get("unrated_lessons_today", 0) for u in users_summary)

    if unrated_total > 0:
        out["checkin_reminder"] = (
            f"{account_name}, du hast heute noch {unrated_total} Stunden zu "
            f"bewerten — kurz anschauen?\n{links['today']}"
        )

    parts_hw = []
    if overdue:
        parts_hw.append(f"{overdue} überfällig")
    if due_today:
        parts_hw.append(f"{due_today} heute fällig")
    if due_tomorrow:
        parts_hw.append(f"{due_tomorrow} für morgen")
    if parts_hw:
        out["homework_reminder"] = (
            f"{account_name}, Hausaufgaben: " + ", ".join(parts_hw)
            + f".\n{links['plan']}"
        )

    if upcoming_subjects:
        sample = ", ".join(upcoming_subjects[:5])
        out["evening_pack"] = (
            f"{account_name}, hast du die Sachen für morgen gepackt? "
            f"Morgen: {sample}.\n{links['week']}"
        )

    if next_exam and next_exam.get("days_until") is not None and 0 <= next_exam["days_until"] <= 7:
        subj = next_exam["subject"] or "Klausur"
        out["exam_reminder"] = (
            f"{account_name}, in {next_exam['days_until']} Tagen "
            f"{subj}-Klausur. Vorbereitung?\n{links['plan']}"
        )

    if absent_open > 0:
        out["catch_up_reminder"] = (
            f"{account_name}, es gibt {absent_open} Stunden, deren Stoff du "
            f"noch nachholen solltest.\n{links['absences']}"
        )

    return out
