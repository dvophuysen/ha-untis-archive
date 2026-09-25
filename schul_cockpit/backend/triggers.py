"""Anstöße: Verarbeitung läuft, sobald sich Quellen ändern, nicht nach der Uhr.

Bisher liefen Sammellauf und Nacharbeit um zwei und um vierzehn Uhr; ein Foto,
ein neuer Untis-Eintrag oder ein neues Buch warteten bis dahin. Jetzt meldet
jede Änderung einen Anstoß für ihr Kind; nach einer kurzen Sammelfrist (damit
fünf Fotos hintereinander einen Lauf ergeben, nicht fünf) startet der
Sammellauf. Untis-Einträge schreibt die Integration ohne Wissen des Add-ons,
darum werden sie alle paar Minuten auf neue Stellen abgehorcht. Gescheiterte
Auswertungen werden nach einer Viertelstunde erneut versucht, höchstens
dreimal je Programmlauf. Die Läufe um zwei und vierzehn Uhr bleiben als Netz.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import closing
from datetime import datetime, timedelta

from .db import webapp_conn
from .learning import now_iso

LOG = logging.getLogger("schul_cockpit.triggers")

# Sammelfrist nach dem letzten Anstoß, in Sekunden.
DEBOUNCE = 90
# Wie oft nach neuen Untis-Stellen geschaut wird.
WATCH_INTERVAL = 300
# Gescheiterte Auswertungen: Wartezeit und Höchstzahl der Wiederholungen.
RETRY_AFTER = timedelta(minutes=15)
RETRY_MAX = 3
RETRY_LIMIT = 5

_PENDING: dict[int, dict] = {}
_LAST: dict[int, dict] = {}
_SEEN: dict[int, str] = {}
_RETRIES: dict[int, int] = {}


def request(account_id: int, reason: str, delay: int = DEBOUNCE) -> None:
    """Einen Sammellauf für dieses Kind vormerken; weitere Anstöße innerhalb der
    Frist verlängern sie nur."""
    due = datetime.now() + timedelta(seconds=delay)
    entry = _PENDING.setdefault(account_id, {"due": due, "reasons": []})
    entry["due"] = due
    if reason not in entry["reasons"]:
        entry["reasons"].append(reason)
    LOG.info("Anstoß für Konto %s: %s (Lauf in %ss)", account_id, reason, delay)


def state(account_id: int | None = None) -> dict:
    """Für die Anzeige: was vorgemerkt ist und was zuletzt lief."""
    if account_id is None:
        return {"pending": {k: {"due": v["due"].isoformat(timespec="seconds"), "reasons": v["reasons"]} for k, v in _PENDING.items()},
                "last": _LAST}
    pending = _PENDING.get(account_id)
    return {"pending": {"due": pending["due"].isoformat(timespec="seconds"), "reasons": pending["reasons"]} if pending else None,
            "last": _LAST.get(account_id)}


def _fingerprint(account_id: int) -> str:
    """Kennung aller Stellen, die Untis und Themenlisten gerade nennen."""
    from . import mentor_context as mc
    from .sources import mentions
    found, _ = mentions(account_id)
    return mc.fingerprint([(f["kind"], f["id"], f["text"]) for f in found])


def watch_untis() -> list[int]:
    """Neue oder geänderte Untis-Einträge erkennen: wer eine andere Kennung als
    beim letzten Blick hat, bekommt einen Anstoß. Der erste Blick merkt nur."""
    from .source_collector import accounts_with_books
    changed = []
    for account_id in accounts_with_books():
        try:
            digest = _fingerprint(account_id)
        except Exception:
            LOG.debug("Untis-Kennung für Konto %s nicht lesbar", account_id, exc_info=True)
            continue
        before = _SEEN.get(account_id)
        _SEEN[account_id] = digest
        if before is not None and before != digest:
            request(account_id, "neue Untis-Einträge")
            changed.append(account_id)
    return changed


def failed_materials(limit: int = RETRY_LIMIT) -> list[tuple[int, int]]:
    """Gescheiterte Auswertungen, die lange genug liegen und noch Versuche haben.

    Die Versuche zählt das Material selbst (material_analysis.may_retry), über
    Neustarts hinweg; _RETRIES begrenzt nur zusätzlich je Programmlauf."""
    from .material_analysis import MAX_ATTEMPTS, may_retry
    cutoff = (datetime.fromisoformat(now_iso()) - RETRY_AFTER).isoformat()
    with closing(webapp_conn()) as conn:
        rows = conn.execute(
            "SELECT m.account_id,m.id,m.analysis_error,m.analysis_state,m.analysis_attempts,m.analysis_failed_at "
            "FROM materials m "
            "JOIN learning_profiles p ON p.account_id=m.account_id AND p.active=1 AND p.ai_enabled=1 "
            # Zeitpunkte, nicht Zeichenketten: updated_at in UTC, die Grenze in Berliner Zeit.
            "WHERE m.hidden=0 AND m.analysis_state='failed' AND julianday(m.updated_at)<julianday(?) "
            "AND COALESCE(m.analysis_attempts,0)<? "
            "ORDER BY m.updated_at LIMIT ?",
            (cutoff, MAX_ATTEMPTS, limit * 3)).fetchall()
    out = []
    for r in rows:
        if not may_retry(r):
            continue
        # Ein erschöpfter KI-Rahmen (429) ist kein Fehler der Seite: so oft wieder
        # versuchen, bis Rahmen frei ist; die Anfrage kostet vorher nichts.
        budget = str(r[2] or "").strip() == "429"
        if budget or _RETRIES.get(r[1], 0) < RETRY_MAX:
            out.append((r[0], r[1]))
        if len(out) >= limit:
            break
    return out


async def retry_failed() -> int:
    from . import material_analysis as analysis
    done = 0
    for account_id, material_id in failed_materials():
        _RETRIES[material_id] = _RETRIES.get(material_id, 0) + 1
        try:
            if await analysis.analyze(account_id, material_id):
                done += 1
                LOG.info("Auswertung von Material %s im %s. Anlauf gelungen", material_id, _RETRIES[material_id])
        except Exception:
            LOG.warning("Wiederholung für Material %s scheiterte", material_id, exc_info=True)
    return done


async def run_pending(now: datetime | None = None) -> list[dict]:
    """Fällige Anstöße ausführen."""
    from .source_collector import collect
    now = now or datetime.now()
    done = []
    for account_id in [k for k, v in list(_PENDING.items()) if v["due"] <= now]:
        entry = _PENDING.pop(account_id)
        started = now_iso()
        try:
            result = await collect(account_id)
            _LAST[account_id] = {"at": started, "reasons": entry["reasons"], "result": {k: result.get(k) for k in ("fetched", "stored", "verified", "links", "skipped")}}
            LOG.info("Sammellauf nach Anstoß (%s) für Konto %s: %s", ", ".join(entry["reasons"]), account_id, _LAST[account_id]["result"])
            done.append(_LAST[account_id])
        except Exception:
            _LAST[account_id] = {"at": started, "reasons": entry["reasons"], "error": "abgebrochen"}
            LOG.warning("Sammellauf nach Anstoß für Konto %s abgebrochen", account_id, exc_info=True)
    return done


async def loop() -> None:
    await asyncio.sleep(60)
    last_watch = datetime.min
    last_retry = datetime.min
    while True:
        try:
            now = datetime.now()
            if (now - last_watch).total_seconds() >= WATCH_INTERVAL:
                last_watch = now
                watch_untis()
            if (now - last_retry).total_seconds() >= RETRY_AFTER.total_seconds():
                last_retry = now
                await retry_failed()
            await run_pending(now)
        except Exception:
            LOG.warning("Anstöße verschoben; nächster Versuch gleich", exc_info=True)
        await asyncio.sleep(20)
