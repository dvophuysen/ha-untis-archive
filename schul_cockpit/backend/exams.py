"""Exam ingestion from a linked HA calendar (e.g. an iServ subscription),
with subject auto-detection, manual overrides and manually added exams.

WebUntis itself is a dead end for exams on the kids' student role (the
dedicated endpoint returns 403, the timetable only spans ±9 days), so the
curated calendar is the single reliable source. Each calendar event is
resolved to exactly one subject — automatically via alias matching, or
manually assigned / dismissed by the user.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta

from .db import history_conn, webapp_conn
from .supervisor_client import SupervisorError, get_supervisor

# Default keywords whose presence means "this calendar entry is not a
# relevant exam for us". Editable per account. (Religion: the kids take
# Werte und Normen instead; the others are non-exam events.)
DEFAULT_EXCLUDE_KEYWORDS = [
    "turnier", "ausflug", "hospitation", "religion", "re-ök", "wandertag",
    "elternabend", "ferien",
]

# Built-in alias seeds keyed by a normalised canonical subject name. Used
# only for subjects the kid actually has (so e.g. Religion never matches
# for a Werte-und-Normen kid). Single letters are intentionally omitted —
# too many false hits.
_SYNONYMS: dict[str, list[str]] = {
    "mathematik": ["ma", "mathe", "mathematik"],
    "deutsch": ["de", "deu", "deutsch"],
    "englisch": ["en", "eng", "englisch"],
    "biologie": ["bi", "bio", "biologie"],
    "chemie": ["ch", "che", "chemie"],
    "physik": ["ph", "phy", "physik"],
    "geschichte": ["ge", "ges", "gesch", "geschichte"],
    "erdkunde": ["ek", "erd", "erdkunde", "geographie", "geografie", "geo"],
    "politik": ["po", "pol", "politik", "powi", "sowi", "politik-wirtschaft"],
    "werte und normen": ["wn", "wun", "werte und normen", "werte&normen", "werte+normen", "wuon"],
    "französisch": ["fr", "franz", "französisch", "franzoesisch"],
    "spanisch": ["spa", "span", "spanisch"],
    "latein": ["la", "lat", "latein"],
    "kunst": ["ku", "kunst", "bk"],
    "musik": ["mu", "mus", "musik"],
    "sport": ["spo", "sport"],
    "informatik": ["if", "inf", "informatik", "iservu"],
    "religion": ["rel", "reli", "religion", "re-ök"],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    return s.strip()


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß0-9]+", _norm(s)))


def account_subjects(account_id: int) -> list[dict]:
    """Distinct subjects the kid actually has (last ~year), with Kürzel."""
    hconn = history_conn()
    try:
        rows = hconn.execute(
            "SELECT subject_untis_id, subject_name, "
            "MAX(payload_json) AS payload_json "
            "FROM lessons WHERE account_id = ? AND subject_untis_id IS NOT NULL "
            "AND date >= date('now','-365 days') "
            "GROUP BY subject_untis_id, subject_name "
            "ORDER BY subject_name",
            (account_id,),
        ).fetchall()
    finally:
        hconn.close()
    from .courses import visible_subject_ids
    visible = visible_subject_ids(account_id)
    out = []
    for r in rows:
        if visible is not None and r["subject_untis_id"] not in visible:
            continue
        short = None
        if r["payload_json"]:
            try:
                su = (json.loads(r["payload_json"]) or {}).get("su")
                if isinstance(su, list) and su and isinstance(su[0], dict):
                    short = su[0].get("name")
            except (json.JSONDecodeError, TypeError):
                pass
        out.append({
            "subject_untis_id": r["subject_untis_id"],
            "subject_name": r["subject_name"],
            "short": short,
        })
    return out


def build_alias_map(account_id: int) -> dict[str, dict]:
    """alias(lower) -> {subject_name, subject_untis_id, multiword: bool}.

    Combines: the kid's real subjects (name + Kürzel), built-in synonyms for
    those subjects, and user-defined aliases."""
    subjects = account_subjects(account_id)
    amap: dict[str, dict] = {}

    def add(alias: str, name: str, sid):
        alias = _norm(alias)
        if len(alias) < 2:
            return
        amap[alias] = {
            "subject_name": name,
            "subject_untis_id": sid,
            "multiword": (" " in alias or "&" in alias or "+" in alias),
        }

    for s in subjects:
        name = s["subject_name"]
        sid = s["subject_untis_id"]
        if not name:
            continue
        add(name, name, sid)
        if s["short"]:
            add(s["short"], name, sid)
        syn = _SYNONYMS.get(_norm(name))
        if syn:
            for a in syn:
                add(a, name, sid)

    # User-defined aliases override / extend.
    conn = webapp_conn()
    try:
        for r in conn.execute(
            "SELECT alias, subject_name, subject_untis_id FROM subject_aliases "
            "WHERE account_id = ?",
            (account_id,),
        ).fetchall():
            add(r["alias"], r["subject_name"], r["subject_untis_id"])
    finally:
        conn.close()
    return amap


def match_subject(summary: str, amap: dict[str, dict]) -> tuple[str, list[dict]]:
    """Returns (status, subjects) where status ∈ {'auto','ambiguous','unmatched'}
    and subjects is the list of distinct matched subjects."""
    norm_full = _norm(summary)
    toks = _tokens(summary)
    matched: dict[int | str, dict] = {}
    for alias, info in amap.items():
        hit = (alias in norm_full) if info["multiword"] else (alias in toks)
        if hit:
            key = info["subject_untis_id"] or info["subject_name"]
            matched[key] = {
                "subject_name": info["subject_name"],
                "subject_untis_id": info["subject_untis_id"],
            }
    subs = list(matched.values())
    if len(subs) == 1:
        return "auto", subs
    if len(subs) > 1:
        return "ambiguous", subs
    return "unmatched", []


def _event_date(ev: dict) -> str | None:
    """Extract YYYY-MM-DD from an HA calendar event (string or dict form)."""
    raw = ev.get("start")
    if isinstance(raw, dict):
        raw = raw.get("dateTime") or raw.get("date")
    if not raw:
        return None
    return str(raw)[:10]


def _source_key(ev: dict) -> str:
    uid = ev.get("uid")
    if uid:
        return f"uid:{uid}"
    basis = f"{ev.get('summary','')}|{_event_date(ev) or ''}"
    return "h:" + hashlib.md5(basis.encode("utf-8")).hexdigest()[:16]


def _get_calendar_config(account_id: int) -> tuple[str | None, list[str]]:
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
        return None, list(DEFAULT_EXCLUDE_KEYWORDS)
    kws = row["exclude_keywords"]
    if kws:
        excludes = [k.strip().lower() for k in kws.split(",") if k.strip()]
    else:
        excludes = list(DEFAULT_EXCLUDE_KEYWORDS)
    return row["ha_entity_id"], excludes


def _overrides(account_id: int) -> dict[str, dict]:
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT source_key, decision, subject_name, subject_untis_id "
            "FROM exam_overrides WHERE account_id = ?",
            (account_id,),
        ).fetchall()
    finally:
        conn.close()
    return {r["source_key"]: dict(r) for r in rows}


def _manual_exams(account_id: int, today_iso: str, end_iso: str) -> list[dict]:
    conn = webapp_conn()
    try:
        rows = conn.execute(
            "SELECT id, exam_date, subject_name, subject_untis_id, title, note "
            "FROM manual_exams WHERE account_id = ? "
            "AND exam_date >= ? AND exam_date <= ? ORDER BY exam_date",
            (account_id, today_iso, end_iso),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


async def resolve_exams(
    account_id: int,
    *,
    days_ahead: int = 90,
    past_days: int = 0,
    diagnostic: bool = False,
) -> dict:
    """Return resolved exams in [today - past_days, today + days_ahead].
    With diagnostic=True, also include hidden (excluded/dismissed/
    unmatched/ambiguous) calendar entries so the user can curate them."""
    today = date.today()
    today_iso = today.isoformat()
    start = today - timedelta(days=past_days)
    start_iso = start.isoformat()
    end = today + timedelta(days=days_ahead)
    end_iso = end.isoformat()

    entity_id, excludes = _get_calendar_config(account_id)
    amap = build_alias_map(account_id)
    overrides = _overrides(account_id)

    relevant: list[dict] = []
    diag: list[dict] = []

    # --- Calendar source ---
    calendar_error = None
    if entity_id:
        sup = get_supervisor()
        if sup.available:
            try:
                events = await sup.get_calendar_events(
                    entity_id,
                    datetime.combine(start, datetime.min.time()).isoformat(),
                    datetime.combine(end, datetime.min.time()).isoformat(),
                )
            except SupervisorError as exc:
                events = []
                calendar_error = str(exc)
            for ev in events:
                d = _event_date(ev)
                if not d:
                    continue
                summary = ev.get("summary") or ev.get("message") or ""
                key = _source_key(ev)
                ov = overrides.get(key)
                entry = {
                    "source": "calendar",
                    "source_key": key,
                    "exam_key": key,
                    "date": d,
                    "title": summary,
                    "subject_name": None,
                    "subject_untis_id": None,
                    "status": None,         # auto|assigned|ambiguous|unmatched|excluded|dismissed
                    "candidates": [],
                }
                if ov and ov["decision"] == "dismissed":
                    entry["status"] = "dismissed"
                elif ov and ov["decision"] == "assigned":
                    entry["status"] = "assigned"
                    entry["subject_name"] = ov["subject_name"]
                    entry["subject_untis_id"] = ov["subject_untis_id"]
                elif any(kw in _norm(summary) for kw in excludes):
                    entry["status"] = "excluded"
                else:
                    status, subs = match_subject(summary, amap)
                    entry["status"] = status
                    entry["candidates"] = subs
                    if status == "auto":
                        entry["subject_name"] = subs[0]["subject_name"]
                        entry["subject_untis_id"] = subs[0]["subject_untis_id"]
                if entry["status"] in ("auto", "assigned"):
                    relevant.append(entry)
                diag.append(entry)

    # --- Manual exams ---
    for m in _manual_exams(account_id, start_iso, end_iso):
        entry = {
            "source": "manual",
            "manual_id": m["id"],
            "exam_key": f"manual:{m['id']}",
            "date": m["exam_date"],
            "title": m["title"] or m["subject_name"],
            "subject_name": m["subject_name"],
            "subject_untis_id": m["subject_untis_id"],
            "note": m["note"],
            "status": "manual",
        }
        relevant.append(entry)
        diag.append(entry)

    relevant.sort(key=lambda e: e["date"])
    diag.sort(key=lambda e: e["date"])

    result = {
        "entity_id": entity_id,
        "exclude_keywords": excludes,
        "calendar_error": calendar_error,
        "exams": relevant,
    }
    if diagnostic:
        result["all_entries"] = diag
    return result
