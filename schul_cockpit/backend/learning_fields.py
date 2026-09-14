"""Themenfelder: ein Ordnungsrahmen über den Teilthemen eines Fachs.

Eine Klassenarbeit dreht sich um ein Feld, geschrieben wird sie über dessen
Einzelaspekte. Das Feld ersetzt die Teile deshalb nicht, es ordnet sie. Geübt,
bewertet und wiederholt werden weiterhin ausschließlich die Teilthemen; das Feld
trägt keinen eigenen Lernstand und keine eigene Aufgabe.

Der nächtliche Lauf gruppiert und sortiert. Er führt nichts zusammen: Zwei
Teilthemen bleiben zwei, auch wenn sie zum selben Feld gehören, weil sonst
verloren ginge, welcher Teil sitzt und welcher nicht.
"""

from __future__ import annotations

import json
import logging
from contextlib import closing
from datetime import date, datetime, timedelta

from . import ai_gateway
from .db import webapp_conn
from .learning import now_iso, today_local
from .mentor_context import practice_subject

LOG = logging.getLogger("schul_cockpit.fields")

# Unter dieser Zahl lohnt kein Feld: drei Titel liest man auch ohne Rahmen.
MIN_TOPICS = 4
# Eine Ordnung, die sich wöchentlich ändert, ist keine Ordnung.
COOLDOWN_DAYS = 7
MAX_TOPICS = 40


def school_year_start(day: date | None = None) -> date:
    day = day or today_local()
    return date(day.year if day.month >= 8 else day.year - 1, 8, 1)


def _profile(conn, account_id: int):
    return conn.execute(
        "SELECT id FROM learning_profiles WHERE account_id=? AND active=1", (account_id,)
    ).fetchone()


def topics_of(conn, profile_id: int, subject: str, since: str) -> list[dict]:
    """Teilthemen eines Fachs im laufenden Schuljahr, mit Beleglage."""
    rows = conn.execute(
        "SELECT t.id,t.title,t.objective,t.field_id,t.field_rank,"
        " (SELECT COUNT(DISTINCT i.lesson_id) FROM learning_discovery_items i WHERE i.topic_id=t.id) AS lessons,"
        " (SELECT MAX(i.rowid) FROM learning_discovery_items i WHERE i.topic_id=t.id) AS seen"
        " FROM learning_topics t WHERE t.profile_id=? AND t.subject=? AND t.updated_at>=?"
        " ORDER BY t.id", (profile_id, subject, since)).fetchall()
    return [dict(r) for r in rows]


def due_subject(conn, profile_id: int, since: str) -> str | None:
    """Das Fach, das heute Nacht an der Reihe ist, oder keines."""
    rows = conn.execute(
        "SELECT t.subject, COUNT(*) AS n, MAX(t.updated_at) AS newest,"
        " SUM(CASE WHEN t.field_id IS NULL THEN 1 ELSE 0 END) AS loose"
        " FROM learning_topics t WHERE t.profile_id=? AND t.updated_at>=?"
        " GROUP BY t.subject", (profile_id, since)).fetchall()
    best = None
    for r in rows:
        if r["n"] < MIN_TOPICS or not practice_subject(r["subject"]):
            continue
        if not r["loose"]:
            continue
        last = conn.execute(
            "SELECT ran_at FROM learning_field_runs WHERE profile_id=? AND subject=?",
            (profile_id, r["subject"])).fetchone()
        if last and last["ran_at"] > (datetime.fromisoformat(now_iso()) - timedelta(days=COOLDOWN_DAYS)).isoformat():
            continue
        if best is None or r["loose"] > best["loose"]:
            best = dict(r)
    return best["subject"] if best else None


INSTRUCTION = (
    "Ordne die Teilthemen eines Schulfachs zu Themenfeldern. Ein Feld ist das, worüber eine "
    "Klassenarbeit geschrieben würde, etwa Bruchrechnung oder Elektrische Stromkreise. "
    "Die Teilthemen bleiben einzeln bestehen und werden einzeln geübt; du fasst sie nicht "
    "zusammen, benennst sie nicht um und lässt keines weg. Jede topic_id kommt genau einmal vor. "
    "Ordne die Teile eines Feldes in der Reihenfolge, in der sie fachlich aufeinander aufbauen, "
    "nicht nach Datum: Grundlagen zuerst, darauf Aufbauendes später. "
    "Ein Feld braucht mindestens zwei Teile. Teile, die zu keinem Feld passen, kommen nach einzeln. "
    "Erfinde keine Inhalte und keine Lehrplanvorgaben. Titel des Feldes kurz und fachlich, "
    "höchstens 60 Zeichen. Antworte ausschließlich als JSON nach diesem Schema: "
    '{"fields":[{"title":"...","topic_ids":[1,2]}],"einzeln":[3]}'
)


def _parse(raw: str, known: set[int]) -> tuple[list[dict], list[int]]:
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    data = json.loads(raw)
    fields, seen = [], set()
    for entry in data.get("fields") or []:
        ids = [int(i) for i in entry.get("topic_ids") or [] if int(i) in known]
        ids = [i for i in ids if i not in seen]
        title = str(entry.get("title") or "").strip()[:60]
        if len(ids) < 2 or not title:
            continue
        seen.update(ids)
        fields.append({"title": title, "topic_ids": ids})
    return fields, sorted(known - seen)


def _store(conn, profile_id: int, subject: str, fields: list[dict], loose: list[int]) -> None:
    stamp = now_iso()
    for entry in fields:
        conn.execute(
            "INSERT INTO learning_fields(profile_id,subject,title,created_at,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(profile_id,subject,title) DO UPDATE SET updated_at=excluded.updated_at",
            (profile_id, subject, entry["title"], stamp, stamp))
        fid = conn.execute(
            "SELECT id FROM learning_fields WHERE profile_id=? AND subject=? AND title=?",
            (profile_id, subject, entry["title"])).fetchone()[0]
        for rank, topic_id in enumerate(entry["topic_ids"], start=1):
            conn.execute("UPDATE learning_topics SET field_id=?,field_rank=? WHERE id=? AND profile_id=?",
                         (fid, rank, topic_id, profile_id))
    for topic_id in loose:
        conn.execute("UPDATE learning_topics SET field_id=NULL,field_rank=0 WHERE id=? AND profile_id=?",
                     (topic_id, profile_id))
    conn.execute("INSERT INTO learning_field_runs(profile_id,subject,ran_at) VALUES(?,?,?) "
                 "ON CONFLICT(profile_id,subject) DO UPDATE SET ran_at=excluded.ran_at",
                 (profile_id, subject, stamp))
    conn.execute("DELETE FROM learning_fields WHERE profile_id=? AND subject=? AND id NOT IN "
                 "(SELECT field_id FROM learning_topics WHERE field_id IS NOT NULL)",
                 (profile_id, subject))


async def consolidate(account_id: int, subject: str | None = None) -> dict:
    """Ein Fach eines Kindes neu ordnen. Ohne Fach wird das fälligste gewählt."""
    since = school_year_start().isoformat()
    with closing(webapp_conn()) as conn:
        profile = _profile(conn, account_id)
        if not profile:
            return {"subject": None, "reason": "kein aktives Schuljahr"}
        subject = subject or due_subject(conn, profile["id"], since)
        if not subject:
            return {"subject": None, "reason": "nichts zu ordnen"}
        topics = topics_of(conn, profile["id"], subject, since)[:MAX_TOPICS]
    if len(topics) < MIN_TOPICS:
        return {"subject": subject, "reason": "zu wenige Teilthemen"}
    context = {"fach": subject, "teilthemen": [
        {"topic_id": t["id"], "titel": t["title"], "ziel": t["objective"][:200], "stunden": t["lessons"]}
        for t in topics]}
    raw, _, _ = await ai_gateway.complete(account_id, "background", INSTRUCTION, context, max_output=2000)
    try:
        fields, loose = _parse(raw, {t["id"] for t in topics})
    except (ValueError, TypeError, KeyError):
        LOG.warning("Themenfelder für %s nicht lesbar", subject)
        return {"subject": subject, "reason": "Antwort nicht lesbar"}
    with closing(webapp_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        _store(conn, profile["id"], subject, fields, loose)
    return {"subject": subject, "fields": len(fields), "topics": len(topics), "einzeln": len(loose)}


def fields_of(account_id: int) -> dict[int, dict]:
    """Feldzuordnung je Thema, samt Deckung des Feldes.

    Die Deckung zählt über alle Teile des Feldes, nicht über die gerade
    angezeigten. Sonst stünde ein dritter Schritt in einem Feld mit zwei
    sichtbaren Teilen.
    """
    with closing(webapp_conn()) as conn:
        profile = _profile(conn, account_id)
        if not profile:
            return {}
        rows = conn.execute(
            "SELECT t.id AS topic_id,t.field_rank,f.id AS field_id,f.title,f.subject "
            "FROM learning_topics t JOIN learning_fields f ON f.id=t.field_id WHERE t.profile_id=?",
            (profile["id"],)).fetchall()
        coverage = conn.execute(
            "SELECT t.field_id AS field_id, COUNT(*) AS parts, SUM(CASE WHEN EXISTS("
            " SELECT 1 FROM learning_plan_links l JOIN mentor_evidence e"
            "  ON e.skill_id=l.skill_id AND e.account_id=l.account_id"
            " WHERE l.account_id=? AND l.goal_key='discovered:'||t.id"
            "  AND e.invalidated=0 AND e.result='correct' AND e.help_used=0"
            ") THEN 1 ELSE 0 END) AS shown"
            " FROM learning_topics t WHERE t.profile_id=? AND t.field_id IS NOT NULL"
            " GROUP BY t.field_id", (account_id, profile["id"])).fetchall()
    counts = {r["field_id"]: (r["parts"], r["shown"] or 0) for r in coverage}
    found = {}
    for r in rows:
        entry = dict(r)
        entry["parts"], entry["shown"] = counts.get(r["field_id"], (0, 0))
        found[r["topic_id"]] = entry
    return found
