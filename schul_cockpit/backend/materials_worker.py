"""Nightly background work: material analysis and the school calendars.

Materials are analysed right away on upload; this is the safety net during the
day and the bounded update at night. The calendars come along because exam
dates move during the year and nobody should have to press a button for that.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import closing
from datetime import datetime, timedelta

from . import learning_fields
from . import material_analysis as analysis
from . import school_calendars
from .db import webapp_conn
from .learning import now_iso, today_local

log = logging.getLogger(__name__)

# Bounded so a large backlog cannot be worked off in one go.
NIGHT_LIMIT = 40
RESCUE_LIMIT = 5
NIGHT_HOUR = 2
CALENDAR_KEY = "calendars:night"
FIELDS_KEY = "fields:night"


def _stuck(limit: int) -> list[tuple[int, int]]:
    """Uploads whose analysis never finished, for example after a restart."""
    cutoff = (datetime.fromisoformat(now_iso()) - timedelta(minutes=10)).isoformat()
    with closing(webapp_conn()) as conn:
        return [(r[0], r[1]) for r in conn.execute(
            "SELECT m.account_id,m.id FROM materials m "
            "JOIN learning_profiles p ON p.account_id=m.account_id AND p.active=1 AND p.ai_enabled=1 "
            # julianday vergleicht Zeitpunkte, nicht Zeichenketten: updated_at
            # steht in UTC, die Grenze in Berliner Zeit. Als Text verglichen galt
            # ein Upload von vor einer Minute schon als hängend und wurde ein
            # zweites Mal ausgewertet, während die erste Lesung noch lief.
            "WHERE m.hidden=0 AND m.analysis_state='pending' AND julianday(m.updated_at)<julianday(?) "
            "ORDER BY m.id LIMIT ?", (cutoff, limit)).fetchall()]


def _last_night_run(key: str = "materials:night") -> str:
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else ""


def _mark_night_run(day: str, key: str = "materials:night") -> None:
    with closing(webapp_conn()) as conn:
        conn.execute("INSERT INTO schema_meta(key,value) VALUES(?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, day))


async def refresh_calendars(day: str) -> None:
    """Once a night, for every child with an IServ access."""
    if _last_night_run(CALENDAR_KEY) == day:
        return
    _mark_night_run(day, CALENDAR_KEY)
    for account_id in school_calendars.configured_accounts():
        try:
            await school_calendars.sync(account_id)
        except Exception:
            # One child's access must not stop the others.
            log.warning("Kalenderabgleich für Konto %s verschoben", account_id)


async def order_topics(day: str) -> None:
    """Ein Fach je Kind und Nacht zu Themenfeldern ordnen.

    Gruppiert und sortiert, führt nichts zusammen: Welcher Teil sitzt und
    welcher nicht, bleibt je Teilthema sichtbar.
    """
    if _last_night_run(FIELDS_KEY) == day:
        return
    _mark_night_run(day, FIELDS_KEY)
    with closing(webapp_conn()) as conn:
        accounts = [r[0] for r in conn.execute(
            "SELECT s.account_id FROM mentor_settings s JOIN learning_profiles p ON p.account_id=s.account_id "
            "WHERE s.enabled=1 AND p.active=1 AND p.ai_enabled=1")]
    for account_id in accounts:
        try:
            result = await learning_fields.consolidate(account_id)
            if result.get("fields"):
                log.info("Themenfelder geordnet: Konto %s, Fach %s", account_id, result["subject"])
        except Exception:
            log.warning("Themenfelder für Konto %s verschoben", account_id)


async def cycle() -> int:
    done = 0
    for account_id, material_id in _stuck(RESCUE_LIMIT):
        if await analysis.analyze(account_id, material_id):
            done += 1
    day = today_local().isoformat()
    if datetime.now().hour >= NIGHT_HOUR:
        await refresh_calendars(day)
        await order_topics(day)
    if datetime.now().hour >= NIGHT_HOUR and _last_night_run() != day:
        _mark_night_run(day)
        for account_id, material_id in analysis.due(NIGHT_LIMIT):
            if await analysis.analyze(account_id, material_id):
                done += 1
            await asyncio.sleep(1)
        log.info("Nächtliche Materialaktualisierung abgeschlossen (%s Einträge)", done)
    return done


async def background_loop() -> None:
    while True:
        await asyncio.sleep(600)
        try:
            await cycle()
        except Exception:
            log.warning("Materialauswertung im Hintergrund verschoben; nächster Versuch später")
