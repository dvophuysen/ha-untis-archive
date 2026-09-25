"""Exam calendar linking, subject overrides, diagnostics.

Exam dates are fetched, never entered by hand: the school keeps them in the
IServ exam plan, and a second place to maintain them only drifts.
"""

from __future__ import annotations

import logging

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import CurrentUser, assert_account_access, get_current_user, require_admin
from ..db import history_conn, webapp_conn
from ..exams import (
    DEFAULT_EXCLUDE_KEYWORDS,
    _norm,
    account_subjects,
    resolve_exams,
)
from ..supervisor_client import SupervisorError, get_supervisor
from .. import exam_meta, lernstand

router = APIRouter()
_LOG = logging.getLogger("schul_cockpit.exams")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_parent(user: CurrentUser) -> None:
    # Mitlesen und Kindmodus gelten als Kind (D183).
    from ..view_mode import acts_as_parent
    if not acts_as_parent(user):
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


def school_year_start(day: date | None = None) -> date:
    """The 1st of August. German school years start there, and the summer
    holidays straddle the turn of the month either way."""
    day = day or date.today()
    return date(day.year if day.month >= 8 else day.year - 1, 8, 1)


def archive_before(account_id: int) -> str | None:
    """Everything before this day counts as a closed school year."""
    conn = webapp_conn()
    try:
        row = conn.execute(
            "SELECT before_date FROM exam_archive WHERE account_id = ?", (account_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["before_date"] if row else None


def _set_archive_before(account_id: int, value: str | None) -> None:
    conn = webapp_conn()
    try:
        with conn:
            if value is None:
                conn.execute("DELETE FROM exam_archive WHERE account_id = ?", (account_id,))
            else:
                conn.execute(
                    "INSERT INTO exam_archive(account_id, before_date, updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(account_id) DO UPDATE SET before_date=excluded.before_date,"
                    "updated_at=excluded.updated_at", (account_id, value, _now()))
    finally:
        conn.close()


# Was vor Monaten geübt wurde, sagt über die nächste Arbeit wenig. Die Messung
# betrachtet deshalb ein Fenster, nicht die gesamte Vergangenheit.
PRACTICE_DAYS = 60


def scope_start(subject: str | None, exam_date: str, entries: list[dict]) -> str:
    """Ab wann der Stoff für diese Arbeit zählt.

    Angenommen wird: alles, was seit der letzten Arbeit desselben Fachs
    unterrichtet wurde, sonst seit Schuljahresbeginn. Eine Eingrenzung durch die
    Lehrkraft gibt es vorher nicht, und ohne Annahme lässt sich nicht vorbereiten.
    """
    year = school_year_start(date.fromisoformat(exam_date)).isoformat()
    previous = [e.get("date") for e in entries
                if e.get("subject_name") == subject and e.get("date") and e["date"] < exam_date]
    # Eine Arbeit des vorigen Schuljahres beginnt kein Fenster: Über die Ferien
    # hinweg wäre der Stoff des alten Jahrgangs mitgezählt worden.
    return max([year, *previous]) if previous else year


def _shown_topics(conn, account_id: int, topic_ids: set[int]) -> set[int]:
    """Teilthemen, zu denen ohne Hilfe eine richtige Antwort belegt ist."""
    if not topic_ids:
        return set()
    marks = ",".join("?" * len(topic_ids))
    rows = conn.execute(
        f"SELECT DISTINCT CAST(substr(l.goal_key,12) AS INTEGER) AS topic_id FROM learning_plan_links l "
        f"JOIN mentor_evidence e ON e.skill_id=l.skill_id AND e.account_id=l.account_id "
        f"WHERE l.account_id=? AND l.goal_key LIKE 'discovered:%' AND e.invalidated=0 "
        f"AND e.result='correct' AND e.help_used=0 "
        f"AND CAST(substr(l.goal_key,12) AS INTEGER) IN ({marks})",
        (account_id, *sorted(topic_ids))).fetchall()
    return {r["topic_id"] for r in rows}


def exam_scope(account_id: int, subject: str | None, since: str, until: str) -> dict | None:
    """Der angenommene Stoff einer Arbeit: alle Themen des Fachs im Zeitraum."""
    if not subject:
        return None
    try:
        with closing(history_conn()) as hconn:
            lessons = [r["id"] for r in hconn.execute(
                "SELECT id FROM lessons WHERE account_id=? AND subject_name=? AND date>=? AND date<=?",
                (account_id, subject, since, until)).fetchall()]
    except sqlite3.Error:
        return None
    if not lessons:
        return {"since": since, "topics": [], "parts": 0, "shown": 0, "verified": False}
    conn = webapp_conn()
    try:
        marks = ",".join("?" * len(lessons))
        rows = conn.execute(
            f"SELECT DISTINCT t.id, t.title, t.field_id, f.title AS field FROM learning_discovery_items i "
            f"JOIN learning_topics t ON t.id=i.topic_id LEFT JOIN learning_fields f ON f.id=t.field_id "
            f"WHERE i.account_id=? AND i.lesson_id IN ({marks})", (account_id, *lessons)).fetchall()
        topics = [dict(r) for r in rows]
        shown = _shown_topics(conn, account_id, {r["id"] for r in topics})
        by_topic: dict[int, list[int]] = {}
        for r in conn.execute(
                f"SELECT topic_id, lesson_id FROM learning_discovery_items WHERE account_id=? AND lesson_id IN ({marks}) AND topic_id IS NOT NULL",
                (account_id, *lessons)):
            by_topic.setdefault(r["topic_id"], []).append(r["lesson_id"])
    finally:
        conn.close()
    for entry in topics:
        entry["shown"] = entry["id"] in shown
        entry["lesson_ids"] = by_topic.get(entry["id"], [])
    topics.sort(key=lambda e: ((e["field"] or "\uffff").casefold(), e["title"].casefold()))
    return {"since": since, "topics": topics, "parts": len(topics),
            "shown": sum(1 for e in topics if e["shown"]), "verified": False}


def practice_by_subject(account_id: int, days: int = PRACTICE_DAYS) -> dict[str, dict]:
    """What has actually been practised per subject, as measured, not as felt.

    The self-assessment stays useful, but it is a feeling. These numbers come
    from the mentor's own records: units held, topics shown without help, and
    practice papers written, each within the window.
    """
    found: dict[str, dict] = {}
    since = (date.today() - timedelta(days=days)).isoformat()
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT subject, COUNT(*) AS units, MAX(updated_at) AS last_at FROM mentor_sessions "
            "WHERE account_id=? AND is_test=0 AND is_demo=0 AND updated_at>=? GROUP BY subject",
            (account_id, since)
        ).fetchall()
        for r in rows:
            found.setdefault(_norm(r["subject"]), {})["units"] = r["units"]
            found[_norm(r["subject"])]["last_at"] = r["last_at"]
        for r in conn.execute(
            "SELECT s.subject AS subject, COUNT(DISTINCT s.id) AS shown FROM mentor_skills s "
            "JOIN mentor_evidence e ON e.skill_id=s.id AND e.account_id=s.account_id "
            "WHERE s.account_id=? AND e.invalidated=0 AND e.result='correct' AND e.help_used=0 "
            "AND e.created_at>=? GROUP BY s.subject", (account_id, since)
        ).fetchall():
            found.setdefault(_norm(r["subject"]), {})["independent"] = r["shown"]
        for r in conn.execute(
            "SELECT x.subject AS subject, COUNT(*) AS papers FROM mentor_exam_attempts a "
            "JOIN mentor_exams x ON x.id=a.exam_id WHERE a.account_id=? AND a.submitted_at IS NOT NULL "
            "AND a.submitted_at>=? GROUP BY x.subject", (account_id, since)
        ).fetchall():
            found.setdefault(_norm(r["subject"]), {})["papers"] = r["papers"]
    finally:
        conn.close()
    for entry in found.values():
        entry["days"] = days
        entry.setdefault("units", 0)
        entry.setdefault("independent", 0)
        entry.setdefault("papers", 0)
        entry.setdefault("last_at", None)
    return found


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
    from ..erlass import resolve_section
    from ..grades import display_label, options as grade_options

    today_iso = date.today().isoformat()
    section, _kl, _src = resolve_section(account_id)
    practice = practice_by_subject(account_id)

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
        if e["date"] >= today_iso:
            e["practice"] = practice.get(_norm(e.get("subject_name") or ""))
            since = scope_start(e.get("subject_name"), e["date"], data["exams"])
            e["scope"] = exam_scope(account_id, e.get("subject_name"), since, e["date"])
            # Liegt das Material für diesen Stoff vor? Fehlt etwas, führt der
            # Weg auf die Einkaufsliste des Fachs.
            try:
                from .. import sources
                e["sources"] = sources.exam_sources(account_id, e.get("subject_name"), since, e["date"])
            except Exception:
                _LOG.warning("Quellenstand für die Arbeit in %s nicht berechenbar", e.get("subject_name"), exc_info=True)
                e["sources"] = None
            # Die Themen der offiziellen Themenliste mit ihrer Stufe. Ein Modellaufruf
            # entsteht nur, wenn sich der Text der Liste geändert hat.
            try:
                from .. import mentor_opening
                mentor_opening.remember_exam(account_id, e["exam_key"], e["date"])
                exam_meta.remember(account_id, e["exam_key"], e.get("title"))
                await lernstand.ensure_topics(account_id, e["exam_key"], e.get("subject_name"), since, e["date"])
                # Ohne Themenliste werden die angenommenen Themen aus dem Unterricht
                # genauso geführt: mit Stufe, Stellen und Üben-Knopf.
                lernstand.ensure_assumed_topics(account_id, e["exam_key"], e.get("subject_name"), e.get("scope"))
                e["topics"] = lernstand.topics_for(account_id, e["exam_key"], e.get("subject_name"))
                e["stages"] = lernstand.stage_counts(e["topics"])
            except Exception:
                _LOG.warning("Themen der Arbeit in %s nicht lesbar", e.get("subject_name"), exc_info=True)
                e["topics"], e["stages"] = [], None
        if e["date"] >= today_iso:
            meta = exam_meta.get(account_id, e["exam_key"]) if e.get("exam_key") else {}
            e["oral"] = bool(meta.get("oral")) or exam_meta.is_oral_title(e.get("title"))
            e["note"] = meta.get("note") or ""
        (upcoming if e["date"] >= today_iso else past).append(e)

    cutoff = archive_before(account_id)
    archived = [e for e in past if cutoff and e["date"] < cutoff]
    past = [e for e in past if not (cutoff and e["date"] < cutoff)]

    upcoming.sort(key=lambda e: e["date"])              # soonest first
    past.sort(key=lambda e: e["date"], reverse=True)    # most recent first
    return {
        "calendar_error": data.get("calendar_error"),
        "entity_id": data.get("entity_id"),
        "section": section,
        "grade_options": grade_options(section),
        "upcoming": upcoming,
        "past": past,
        "archive_before": cutoff,
        "archived_count": len(archived),
        "school_year_start": school_year_start().isoformat(),
    }


class ArchiveIn(BaseModel):
    # Ohne Datum wird zum Beginn des laufenden Schuljahres abgeschlossen.
    before: str | None = None
    clear: bool = False


@router.get("/accounts/{account_id}/exams/archive")
async def exams_archive(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Closed school years: still readable, out of the way."""
    assert_account_access(user, account_id)
    cutoff = archive_before(account_id)
    if not cutoff:
        return {"archive_before": None, "exams": []}
    from ..erlass import resolve_section
    from ..grades import display_label

    section, _kl, _src = resolve_section(account_id)
    data = await resolve_exams(account_id, days_ahead=0, past_days=6 * 365)
    prog = _progress_map(account_id)
    exams = []
    for e in data["exams"]:
        if e["date"] >= cutoff:
            continue
        p = prog.get(e.get("exam_key"), {})
        exams.append({**e, "learn_state": p.get("learn_state"),
                      "grade_points": p.get("grade_points"),
                      "grade_label": display_label(p.get("grade_points"), section)})
    exams.sort(key=lambda e: e["date"], reverse=True)
    return {"archive_before": cutoff, "exams": exams}


@router.post("/accounts/{account_id}/exams/archive")
def set_archive(
    account_id: int,
    body: ArchiveIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Close the school year, or open the archive again."""
    assert_account_access(user, account_id)
    _require_parent(user)
    if body.clear:
        _set_archive_before(account_id, None)
        return {"archive_before": None}
    before = body.before or school_year_start().isoformat()
    try:
        date.fromisoformat(before)
    except ValueError:
        raise HTTPException(status_code=422, detail="Datum nicht lesbar") from None
    _set_archive_before(account_id, before)
    return {"archive_before": before}


class TopicIn(BaseModel):
    exam_key: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=2, max_length=120)
    detail: str = Field(default="", max_length=400)


class SelfViewIn(BaseModel):
    value: str | None = Field(default=None, pattern="^(unsicher|mittel|sicher)$")


@router.post("/accounts/{account_id}/exams/topics", status_code=201)
def add_topic(account_id: int, body: TopicIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Ein Thema von Hand ergänzen, etwa wenn die Lehrkraft es mündlich genannt hat."""
    assert_account_access(user, account_id)
    topic = lernstand.add_manual(account_id, body.exam_key, body.subject, body.title.strip(), body.detail.strip())
    if not topic:
        raise HTTPException(409, "Dieses Thema steht schon auf der Liste.")
    return lernstand.public(topic)


class NoteIn(BaseModel):
    exam_key: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=exam_meta.NOTE_MAX)


@router.post("/accounts/{account_id}/exams/note")
def set_note(account_id: int, body: NoteIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Hinweise der Eltern zu einer Arbeit, etwa worüber in der Sprechprüfung gesprochen wird (D193)."""
    assert_account_access(user, account_id)
    _require_parent(user)
    return exam_meta.set_note(account_id, body.exam_key, body.note)


@router.delete("/accounts/{account_id}/exams/topics/{topic_id}")
def delete_topic(account_id: int, topic_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    with closing(webapp_conn()) as conn, conn:
        gone = conn.execute("DELETE FROM exam_topics WHERE id=? AND account_id=?", (topic_id, account_id)).rowcount
    if not gone:
        raise HTTPException(404, "Thema nicht gefunden.")
    return {"ok": True}


@router.post("/accounts/{account_id}/exams/topics/{topic_id}/self-view")
def set_self_view(account_id: int, topic_id: int, body: SelfViewIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Das Gefühl des Kindes zu einem Thema: sortiert, beweist nichts."""
    assert_account_access(user, account_id)
    with closing(webapp_conn()) as conn, conn:
        changed = conn.execute("UPDATE exam_topics SET self_view=?,updated_at=? WHERE id=? AND account_id=?",
                               (body.value, _now(), topic_id, account_id)).rowcount
        row = conn.execute("SELECT * FROM exam_topics WHERE id=?", (topic_id,)).fetchone()
    if not changed or not row:
        raise HTTPException(404, "Thema nicht gefunden.")
    return lernstand.public(dict(row))


@router.get("/accounts/{account_id}/exams/topics/{topic_id}/events")
def topic_events(account_id: int, topic_id: int, user: CurrentUser = Depends(get_current_user)) -> dict:
    assert_account_access(user, account_id)
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM exam_topics WHERE id=? AND account_id=?", (topic_id, account_id)).fetchone()
        if not row:
            raise HTTPException(404, "Thema nicht gefunden.")
        events = [dict(r) for r in conn.execute(
            "SELECT id,session_id,stage_before,stage_after,reason,created_at FROM topic_events WHERE topic_id=? ORDER BY id", (topic_id,))]
        answers = [dict(r) for r in conn.execute(
            "SELECT session_id,task_kind,result,help_used,seconds,edits,re_explained,created_at FROM topic_answers WHERE topic_id=? ORDER BY id", (topic_id,))]
    return {"topic": lernstand.public(dict(row)), "events": events, "answers": answers}


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
    data["archive_before"] = archive_before(account_id)
    data["school_year_start"] = school_year_start().isoformat()
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


# Zusätzliche Termine von Hand: ausschließlich für Arbeiten, die nicht im
# IServ-Klausurplan stehen. Was von dort kommt, wird abgerufen und darf hier
# nicht zweitgepflegt werden — deshalb die Prüfung in _clashes_with_plan.


class ManualExamIn(BaseModel):
    exam_date: str  # YYYY-MM-DD
    subject_name: str
    subject_untis_id: int | None = None
    title: str | None = None
    note: str | None = None


class ManualExamPatch(BaseModel):
    # Alle Felder optional — nur das wird gepatcht, was angegeben ist.
    exam_date: str | None = None
    subject_name: str | None = None
    subject_untis_id: int | None = None
    title: str | None = None
    note: str | None = None


def _plan_entry(account_id: int, day: str, subject_name: str | None) -> str | None:
    """The exam plan's own entry for that day and subject, if there is one."""
    from ..exams import build_alias_map, match_subject
    from .. import school_calendars

    amap = build_alias_map(account_id)
    wanted = (subject_name or "").casefold()
    for event in school_calendars.events(account_id, day, day, role="exam"):
        status, subs = match_subject(event["summary"], amap)
        names = {s["subject_name"].casefold() for s in subs}
        if not wanted or wanted in names:
            return event["summary"]
    return None


@router.post("/accounts/{account_id}/manual-exams", status_code=201)
def add_manual_exam(
    account_id: int,
    body: ManualExamIn,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    assert_account_access(user, account_id)
    _require_parent(user)
    # Only for what the exam plan does not carry; otherwise the same date would
    # be maintained in two places and drift apart.
    clash = _plan_entry(account_id, body.exam_date, body.subject_name)
    if clash:
        raise HTTPException(
            status_code=409,
            detail=f"Dieser Termin steht bereits im IServ-Klausurplan: „{clash}“. "
                   "Von Hand werden nur Arbeiten eingetragen, die dort fehlen.")
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


@router.patch("/accounts/{account_id}/manual-exams/{exam_id}")
def update_manual_exam(
    account_id: int,
    exam_id: int,
    body: ManualExamPatch,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Termin verschieben / Felder anpassen. Nur Eltern/Admin."""
    assert_account_access(user, account_id)
    _require_parent(user)
    fields: list[tuple[str, str | int | None]] = []
    if body.exam_date is not None:
        clash = _plan_entry(account_id, body.exam_date, body.subject_name)
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"An diesem Tag steht schon ein Termin im IServ-Klausurplan: „{clash}“.")
        fields.append(("exam_date", body.exam_date))
    if body.subject_name is not None:
        fields.append(("subject_name", body.subject_name))
    if body.subject_untis_id is not None or body.subject_name is not None:
        # subject_untis_id mit dem Subject-Wechsel zusammen ziehen;
        # explizit None würde sonst die Zuordnung wegräumen.
        fields.append(("subject_untis_id", body.subject_untis_id))
    if body.title is not None:
        fields.append(("title", body.title))
    if body.note is not None:
        fields.append(("note", body.note))
    if not fields:
        return {"ok": True, "updated": 0}
    set_clause = ", ".join(f"{c} = ?" for c, _ in fields)
    params = [v for _, v in fields] + [account_id, exam_id]
    conn = webapp_conn()
    try:
        cur = conn.execute(
            f"UPDATE manual_exams SET {set_clause} "
            "WHERE account_id = ? AND id = ?",
            params,
        )
        updated = cur.rowcount
    finally:
        conn.close()
    if updated == 0:
        raise HTTPException(status_code=404, detail="Termin nicht gefunden")
    return {"ok": True, "updated": updated}
