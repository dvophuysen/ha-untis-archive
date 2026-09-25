"""Was ein Elternteil tun muss oder sollte (D183, „Erledigen“).

Die Eltern-Aufgaben lagen verstreut: Fotos in den Materialien, Gegenlesen an
Themenzetteln, Termine in der Arbeiten-Verwaltung, Anfangsstand und
Kostensätze tief im Lernbegleiter. Hier stehen sie in einer Liste, je Kind
gruppiert, mit einem Satz Grund und dem Sprung zur Aktion in der Elternansicht.
Gerechnet wird nur aus dem Bestand; kein Modellaufruf, nichts wird angestoßen.

Jeder Eintrag: ``key``, ``kind``, ``level`` (``block`` vor allem anderen,
``todo`` sonst), ``title``, ``reason`` (ein Satz) und ``action`` mit ``label``
und dem Ziel ``page``/``args``/``section``/``query``.
"""
from __future__ import annotations

import logging
from contextlib import closing
from datetime import date, timedelta

from . import ai_gateway as ai
from . import materials as store
from . import sources
from .db import history_conn, webapp_conn
from .subject_names import label as subject_label

_LOG = logging.getLogger(__name__)

EXAM_DAYS = 14          # Material für Arbeiten der nächsten zwei Wochen
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Die Arten, die „Scannen“ anbietet, mit der Materialart dahinter.
SCAN_KINDS = {"book_page": "Buchseite", "worksheet": "Arbeitsblatt", "exam_notice": "Themenzettel",
              "vocab": "Vokabelliste", "graded": "Korrigierte Arbeit", "other": "Sonstiges"}


def action(label: str, page: str, *args, section: str | None = None, **query) -> dict:
    return {"label": label, "page": page, "args": [str(a) for a in args], "section": section,
            "query": {k: str(v) for k, v in query.items() if v not in (None, "")}}


def item(key: str, kind: str, title: str, reason: str, act: dict, level: str = "todo") -> dict:
    return {"key": key, "kind": kind, "level": level, "title": title, "reason": reason, "action": act}


def _day(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m.')}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def needs_review_count(account_id: int) -> int:
    """Lesungen, die ein Elternteil gegenlesen soll, wie „Bitte gegenlesen“ in
    den Materialien (ohne die Prüfung der Themenzettel gegen den Unterricht,
    die steht bei der Arbeit)."""
    with closing(webapp_conn()) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(materials)") if r[1] != "file_bytes"]
        rows = conn.execute(
            f"SELECT {','.join(cols)} FROM materials WHERE account_id=? AND hidden=0 AND verified=0 "
            "AND analysis_state='ready' AND COALESCE(origin,'')!='book_fetch' AND kind!='toc'",
            (account_id,)).fetchall()
    return sum(1 for r in rows if store.needs_review(r))


def exam_items(account_id: int, exams: list[dict], entries: list[dict], today: date) -> list[dict]:
    """Fehlendes Material, ungeprüfte Themenzettel und Seiten, die auf freien
    KI-Rahmen warten, für die Arbeiten der nächsten zwei Wochen."""
    from .routers.exams import scope_start
    out = []
    horizon = (today + timedelta(days=EXAM_DAYS)).isoformat()
    for e in sorted(exams, key=lambda x: x["date"]):
        if not (today.isoformat() <= e["date"] <= horizon):
            continue
        subject = e.get("subject_name") or ""
        if not subject:
            continue
        name = subject_label(subject)
        key = e.get("exam_key") or f"{subject}:{e['date']}"
        try:
            src = sources.exam_sources(account_id, subject, scope_start(subject, e["date"], entries), e["date"]) or {}
        except Exception:
            _LOG.warning("Quellenstand der Arbeit in %s nicht lesbar", subject, exc_info=True)
            continue
        when = f"Arbeit am {_day(e['date'])}"
        missing = src.get("missing_items") or []
        if src.get("missing"):
            where = " · ".join(f"{m['label']} {m['pages_label']}" for m in missing[:2])
            out.append(item(f"missing:{key}", "missing_material", f"Material für {name} fotografieren",
                            f"{_plural(src['missing'], 'Seite fehlt', 'Seiten fehlen')} für die {when}"
                            + (f": {where}." if where else "."),
                            action("Scannen", "scannen", acc=account_id, art="book_page", fach=subject)))
        if src.get("notice") and src.get("notice_verified") is False:
            out.append(item(f"notice:{key}", "notice_check", f"Themenzettel {name} gegenlesen",
                            f"Eine Seitenzahl auf dem Zettel zur {when} kennt der Unterricht nicht.",
                            action("Gegenlesen", "materialien", section="gegenlesen", material=src.get("notice_id"))))
        waiting = [p for p in src.get("pending_items") or [] if p.get("kind") == "budget"]
        if waiting:
            out.append(item(f"budget:{key}", "budget_wait", f"{name}: Seiten warten auf KI-Rahmen",
                            f"{_plural(len(waiting), 'Seite ist', 'Seiten sind')} für die {when} da, "
                            "aber der KI-Rahmen ist aufgebraucht.",
                            action("KI-Rahmen ansehen", "einstellen", section="ki")))
    return out


def calendar_items(account_id: int, entries: list[dict], today: date) -> list[dict]:
    """Kalendertermine ohne erkanntes Fach, wie „Bitte zuordnen“ in der
    Arbeiten-Verwaltung; nur kommende."""
    open_ = [e for e in entries if e.get("source") == "calendar" and e.get("status") in ("unmatched", "ambiguous")
             and (e.get("date") or "") >= today.isoformat()]
    if not open_:
        return []
    first = sorted(open_, key=lambda e: e.get("date") or "")[0]
    return [item("calendar", "calendar_assign", f"{_plural(len(open_), 'Termin', 'Termine')} zuordnen",
                 f"Bei „{first.get('title') or 'Termin'}“ am {_day(first['date'])}"
                 + (" und weiteren" if len(open_) > 1 else "") + " ist kein Fach erkannt.",
                 action("Zuordnen", "exams", section="zuordnen"))]


def learning_items(account_id: int) -> list[dict]:
    with closing(webapp_conn()) as conn:
        profile = conn.execute("SELECT school_year,ai_enabled FROM learning_profiles WHERE account_id=? AND active=1",
                               (account_id,)).fetchone()
    target = action("Lernrahmen öffnen", "learning", "legacy", tab="manage")
    if not profile:
        return [item("profile", "learning_frame", "Lernrahmen einrichten",
                     "Für dieses Schuljahr gibt es noch keinen Lernrahmen; ohne ihn übt der Lernbegleiter nicht.", target)]
    if not profile["ai_enabled"]:
        return [item("ai", "learning_ai", "KI für das Schuljahr erlauben",
                     f"Im Lernrahmen {profile['school_year']} ist die KI aus; Lernbegleiter und Auswertung ruhen.", target)]
    return []


def household_items(status: dict | None = None) -> list[dict]:
    """KI-Rahmen der Familie: Anfangsstand und Kostensätze."""
    try:
        status = status or ai.status()
    except Exception:
        _LOG.warning("KI-Rahmen nicht lesbar", exc_info=True)
        return []
    out = []
    target = action("KI-Rahmen öffnen", "einstellen", section="ki")
    if not status.get("opening_confirmed", True):
        out.append(item("opening", "ai_opening", "Anfangsstand der KI-Kosten bestätigen",
                        "Vor der Verbrauchserfassung gab es schon Aufrufe; der Monatsstand ist sonst zu niedrig.", target))
    if not status.get("rate_available", True):
        out.append(item("rates", "ai_rates", "Kostensätze prüfen",
                        "Für das Hauptmodell fehlt ein Kostensatz; neue KI-Aufrufe warten darauf.", target))
    return out


def blocking(user, account_ids: list[int]) -> tuple[list[dict], set[int]]:
    """Verwaiste Verlinkungen und fehlende Einrichtung stehen ganz oben."""
    out = []
    names: dict[int, str] = {}
    if account_ids:
        with closing(history_conn()) as conn:
            names = {r["id"]: r["name"] for r in conn.execute(
                f"SELECT id,name FROM accounts WHERE id IN ({','.join('?' * len(account_ids))})", account_ids)}
    stale = [a for a in account_ids if a not in names]
    if stale:
        out.append(item("stale", "stale_links", f"{_plural(len(stale), 'Kind-Verlinkung', 'Kind-Verlinkungen')} ins Leere",
                        "Ein Kind fehlt gerade in der App, meist nach Schuljahreswechsel oder Neueinrichtung.",
                        action("Im Setup prüfen" if user.is_admin else "Admin fragen", "setup" if user.is_admin else "overview"),
                        level="block"))
    if user.is_admin:
        with closing(webapp_conn()) as conn:
            pending = conn.execute("SELECT COUNT(*) FROM users WHERE role='pending'").fetchone()[0]
            linked = conn.execute("SELECT COUNT(*) FROM user_account_links").fetchone()[0]
        if pending or not linked:
            out.append(item("setup", "setup", "Einrichtung abschließen",
                            f"{_plural(pending, 'neuer Nutzer wartet', 'neue Nutzer warten')} auf eine Zuordnung." if pending
                            else "Noch ist kein Kind verlinkt.", action("Setup öffnen", "setup"), level="block"))
    return out, set(names)


async def collect(user, account_ids: list[int], today: date) -> dict:
    from .exams import resolve_exams
    import asyncio
    blocks, known = blocking(user, account_ids)
    with closing(history_conn()) as conn:
        names = {r["id"]: r["name"] for r in conn.execute(
            f"SELECT id,name FROM accounts WHERE id IN ({','.join('?' * max(1, len(known)))}) ORDER BY name",
            sorted(known) or [-1])}
    kids = []
    for account_id, name in names.items():
        items: list[dict] = []
        try:
            data = await resolve_exams(account_id, days_ahead=EXAM_DAYS, past_days=365, diagnostic=True)
        except Exception:
            _LOG.warning("Arbeiten für Konto %s nicht lesbar", account_id, exc_info=True)
            data = {"exams": [], "all_entries": []}
        exams = data.get("exams") or []
        items += await asyncio.to_thread(exam_items, account_id, exams, exams, today)
        try:
            retakes = store.retakes(account_id, limit=10)
        except Exception:
            _LOG.warning("Fotobitten für Konto %s nicht lesbar", account_id, exc_info=True)
            retakes = []
        if retakes:
            first = retakes[0]
            where = f"{first.get('source_label') or 'Buch'} S. {first['source_page']}" if first.get("source_page") else first["title"]
            items.append(item("retake", "retake", f"{_plural(len(retakes), 'Seite', 'Seiten')} neu fotografieren",
                              f"{where}: {first['reason']}", action("Neu fotografieren", "materialien", section="fotos")))
        try:
            review = needs_review_count(account_id)
        except Exception:
            _LOG.warning("Gegenlesen für Konto %s nicht zählbar", account_id, exc_info=True)
            review = 0
        if review:
            items.append(item("review", "needs_review", f"{_plural(review, 'Lesung', 'Lesungen')} gegenlesen",
                              "Beim Lesen der Fotos war die App an einzelnen Stellen unsicher.",
                              action("Gegenlesen", "materialien", section="gegenlesen")))
        items += calendar_items(account_id, data.get("all_entries") or [], today)
        items += learning_items(account_id)
        for it in items:
            it["account_id"] = account_id
        kids.append({"account_id": account_id, "name": name, "items": items})
    household = household_items()
    total = len(blocks) + len(household) + sum(len(k["items"]) for k in kids)
    return {"today": today.isoformat(), "total": total, "blocking": blocks, "household": household, "kids": kids}
