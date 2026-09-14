"""Background analysis for materials: a safety net during the day, a bounded
update at night. Uploads themselves are analysed right away by the request.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import closing
from datetime import datetime, timedelta

from . import material_analysis as analysis
from .db import webapp_conn
from .learning import now_iso, today_local

log = logging.getLogger(__name__)

# Bounded so a large backlog cannot be worked off in one go.
NIGHT_LIMIT = 40
RESCUE_LIMIT = 5
NIGHT_HOUR = 2


def _stuck(limit: int) -> list[tuple[int, int]]:
    """Uploads whose analysis never finished, for example after a restart."""
    cutoff = (datetime.fromisoformat(now_iso()) - timedelta(minutes=10)).isoformat()
    with closing(webapp_conn()) as conn:
        return [(r[0], r[1]) for r in conn.execute(
            "SELECT m.account_id,m.id FROM materials m "
            "JOIN learning_profiles p ON p.account_id=m.account_id AND p.active=1 AND p.ai_enabled=1 "
            "WHERE m.hidden=0 AND m.analysis_state='pending' AND m.updated_at<? "
            "ORDER BY m.id LIMIT ?", (cutoff, limit)).fetchall()]


def _last_night_run() -> str:
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key='materials:night'").fetchone()
    return row[0] if row else ""


def _mark_night_run(day: str) -> None:
    with closing(webapp_conn()) as conn:
        conn.execute("INSERT INTO schema_meta(key,value) VALUES('materials:night',?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (day,))


async def cycle() -> int:
    done = 0
    for account_id, material_id in _stuck(RESCUE_LIMIT):
        if await analysis.analyze(account_id, material_id):
            done += 1
    day = today_local().isoformat()
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
