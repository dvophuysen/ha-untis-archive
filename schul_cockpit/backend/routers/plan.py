"""Plan v2: MUSS / SOLLTE / KANN instead of a minute budget.

- MUSS heute: overdue + due today + due tomorrow homework, quickest first
  (so small things get done instead of piling up).
- SOLLTE heute: need-driven, max 3 — upcoming exams (from the linked
  calendar / manual), un-caught-up missed material, recurring
  comprehension gaps. Each with a one-line reason.
- KANN heute: optional vocab / practice.
- Pensum-Indikator: a qualitative 'wenig / überschaubar / viel' instead
  of a minute number nobody can estimate honestly.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, assert_account_access, get_current_user
from ..db import history_conn, webapp_conn
from ..exams import resolve_exams

router = APIRouter()


def _row_to_task(r) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "subject_name": r["subject_name"],
        "task_type": r["task_type"],
        "status": r["status"],
        "estimated_minutes": r["estimated_minutes"],
        "due_date": r["due_date"],
        "notes": r["notes"],
        "source": r["source"],
    }


def _quick_rank(t: dict) -> tuple:
    # Quick tasks first: known small estimate < unknown < larger. Then by due.
    est = t.get("estimated_minutes")
    est_rank = est if est is not None else 9999
    return (est_rank, t.get("due_date") or "9999-12-31")


@router.get("/accounts/{account_id}/plan")
async def plan(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    today = date.today()
    today_iso = today.isoformat()
    tomorrow_iso = (today + timedelta(days=1)).isoformat()

    # --- open tasks ---
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE account_id = ? "
            "AND status IN ('open','in_progress') "
            "ORDER BY (due_date IS NULL), due_date",
            (account_id,),
        ).fetchall()
    finally:
        conn.close()
    tasks = [_row_to_task(r) for r in rows]

    must = [t for t in tasks if t["due_date"] and t["due_date"] <= tomorrow_iso]
    must.sort(key=_quick_rank)

    # --- exams (linked calendar + manual) ---
    try:
        exam_data = await resolve_exams(account_id, days_ahead=28)
        exams = exam_data.get("exams", [])
    except Exception:
        exams = []
    upcoming_exams = []
    for e in exams:
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        days = (d - today).days
        if 0 <= days <= 28:
            upcoming_exams.append({**e, "days_until": days})
    upcoming_exams.sort(key=lambda e: e["days_until"])

    # --- SHOULD items (max 3) ---
    should: list[dict] = []

    # 1) Exams within 10 days → prepare.
    for e in upcoming_exams:
        if e["days_until"] <= 10:
            when = (
                "heute" if e["days_until"] == 0
                else "morgen" if e["days_until"] == 1
                else f"in {e['days_until']} Tagen"
            )
            should.append({
                "type": "exam_prep",
                "subject_name": e.get("subject_name"),
                "title": f"{e.get('subject_name') or 'Klausur'} vorbereiten",
                "reason": f"Klausur {when}",
                "days_until": e["days_until"],
                "link": "subjects",
            })

    # 2) Un-caught-up missed material (older than 2 days, last 30 days).
    hconn = history_conn()
    try:
        absent_rows = hconn.execute(
            "SELECT id, subject_name FROM lessons WHERE account_id = ? "
            "AND was_absent = 1 AND (code IS NULL OR LOWER(code) != 'cancelled') "
            "AND date >= date('now','-30 days') AND date <= date('now','-2 days')",
            (account_id,),
        ).fetchall()
        # comprehension gaps
        gap_rows = hconn.execute(
            "SELECT id, subject_name, subject_untis_id FROM lessons "
            "WHERE account_id = ? AND date >= date('now','-28 days')",
            (account_id,),
        ).fetchall()
    finally:
        hconn.close()
    absent_ids = [r["id"] for r in absent_rows]
    absent_subj = {r["id"]: r["subject_name"] for r in absent_rows}

    wconn = webapp_conn()
    try:
        caught = set()
        if absent_ids:
            ph = ",".join("?" for _ in absent_ids)
            caught = {
                r["lesson_id"]
                for r in wconn.execute(
                    f"SELECT DISTINCT lesson_id FROM caught_up "
                    f"WHERE account_id = ? AND lesson_id IN ({ph})",
                    [account_id, *absent_ids],
                ).fetchall()
            }
        open_catchup = [lid for lid in absent_ids if lid not in caught]
        if open_catchup:
            should.append({
                "type": "catch_up",
                "subject_name": None,
                "title": "Versäumten Stoff nachholen",
                "reason": f"{len(open_catchup)} Stunde(n) seit Fehlzeit offen",
                "link": "absences",
            })

        # 3) Comprehension gaps: subjects with >=3 low ratings in 4 weeks.
        gap_lesson_ids = [r["id"] for r in gap_rows]
        subj_of = {r["id"]: r["subject_name"] for r in gap_rows}
        low_by_subject: dict[str, int] = defaultdict(int)
        if gap_lesson_ids:
            ph = ",".join("?" for _ in gap_lesson_ids)
            for r in wconn.execute(
                f"SELECT lesson_id FROM lesson_checkins "
                f"WHERE account_id = ? AND user_id = ? AND rating <= 2 "
                f"AND lesson_id IN ({ph})",
                [account_id, user.id, *gap_lesson_ids],
            ).fetchall():
                s = subj_of.get(r["lesson_id"])
                if s:
                    low_by_subject[s] += 1
    finally:
        wconn.close()

    for subj, cnt in sorted(low_by_subject.items(), key=lambda x: -x[1]):
        if cnt >= 3:
            should.append({
                "type": "understanding",
                "subject_name": subj,
                "title": f"{subj} wiederholen",
                "reason": f"{cnt}× zuletzt unsicher",
                "link": "subjects",
            })

    # Dedup by (type, subject) and cap at 3, exams first (already ordered).
    seen = set()
    deduped = []
    for s in should:
        key = (s["type"], s.get("subject_name"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)
    should = deduped[:3]

    # --- workload indicator (qualitative) ---
    n = len(must)
    if n == 0:
        workload = "frei"
    elif n <= 2:
        workload = "wenig"
    elif n <= 4:
        workload = "überschaubar"
    else:
        workload = "viel"

    return {
        "date": today_iso,
        "workload": workload,
        "must": must,
        "should": should,
        "upcoming_exams": upcoming_exams,
    }
