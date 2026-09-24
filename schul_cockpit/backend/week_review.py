"""Der Wochenrückblick für Eltern: wenige Aussagen aus vorhandenen Zahlen.

Kein Modellaufruf, keine Note, kein Vergleich zwischen Kindern. Jede Zeile
ist eine Beobachtung, die die App ohnehin gespeichert hat: Abende, an denen
vor der Erinnerung alles erledigt war (D34), Stufenwechsel der Themen (D59),
bestandene Kurzprüfungen, Einheiten mit dem Mentor, erledigte Aufgaben, die
Antworten nach der Schule (D69), fehlendes Material für Arbeiten in den
nächsten zwei Wochen und die KI-Kosten. Masterplan Abschnitt 10.
"""

from __future__ import annotations

import logging
from contextlib import closing
from datetime import date, timedelta

from . import day_close
from .db import webapp_conn
from .learning import today_local
from .lernstand import LABELS, PROGRESS
from .subject_names import label as subject_label

LOG = logging.getLogger("schul_cockpit.week_review")
STAGE_WORD = {"neu": "neu", "angefangen": "angefangen", "wackelt": "wackelt", "sitzt": "sitzt", "gefestigt": "gefestigt"}


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def _has(c, table: str) -> bool:
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def _short(day: str) -> str:
    try:
        return date.fromisoformat(day[:10]).strftime("%d.%m.")
    except ValueError:
        return day


async def review(account_id: int, today: date | None = None) -> dict:
    today = today or today_local()
    start, end = week_bounds(today)
    s, e = start.isoformat(), end.isoformat()
    with closing(webapp_conn()) as c:
        events = [dict(r) for r in c.execute(
            "SELECT e.stage_before,e.stage_after,e.reason,e.created_at,t.title,t.subject FROM topic_events e "
            "JOIN exam_topics t ON t.id=e.topic_id WHERE e.account_id=? AND substr(e.created_at,1,10) BETWEEN ? AND ? "
            "ORDER BY e.created_at", (account_id, s, e))]
        # Eine Einheit zählt, wenn das Kind in dieser Woche darin geschrieben
        # hat. Nur abgeschlossene zu zählen verfehlte fast alle: Hausaufgabenhilfe
        # bleibt absichtlich offen (D25), und nur „Für heute fertig" schließt
        # (D73) — der Satz „Keine Einheit mit dem Mentor" stand deshalb meist da,
        # obwohl gearbeitet wurde.
        active = ("SELECT DISTINCT session_id FROM mentor_messages WHERE account_id=? AND role='user' "
                  "AND substr(created_at,1,10) BETWEEN ? AND ?")
        units = c.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(elapsed_seconds),0) AS sec FROM mentor_sessions "
            f"WHERE account_id=? AND is_test=0 AND is_demo=0 AND id IN ({active})",
            (account_id, account_id, s, e)).fetchone()
        unit_subjects = [r[0] for r in c.execute(
            "SELECT DISTINCT subject FROM mentor_sessions WHERE account_id=? AND is_test=0 AND is_demo=0 "
            f"AND id IN ({active}) ORDER BY subject", (account_id, account_id, s, e))]
        homework_done = c.execute(
            "SELECT COUNT(*) FROM tasks WHERE account_id=? AND status='done' AND substr(completed_at,1,10) BETWEEN ? AND ?",
            (account_id, s, e)).fetchone()[0]
        overdue = c.execute(
            "SELECT COUNT(*) FROM tasks WHERE account_id=? AND status IN ('open','in_progress') AND due_date IS NOT NULL AND due_date<?",
            (account_id, today.isoformat())).fetchone()[0]
        afternoon = [dict(r) for r in c.execute(
            "SELECT school_day,answer FROM afternoon_checks WHERE account_id=? AND school_day BETWEEN ? AND ?",
            (account_id, s, e))] if _has(c, "afternoon_checks") else []
        cost_micro = c.execute(
            # Wie das Gateway: Freigegebene Aufrufe (abgelehnt, keine Tokens) kosten nichts.
            "SELECT COALESCE(SUM(CASE WHEN status='settled' THEN charged_micro WHEN status='released' THEN 0 "
            "ELSE reserved_micro END),0) FROM mentor_ai_calls "
            "WHERE account_id=? AND day BETWEEN ? AND ?", (account_id, s, e)).fetchone()[0]
        vocab = None
        if _has(c, "vocab_attempts"):
            row = c.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(result='correct'),0) AS ok, "
                "COALESCE(SUM(result!='correct' AND TRIM(answer)=''),0) AS open FROM vocab_attempts "
                "WHERE account_id=? AND substr(created_at,1,10) BETWEEN ? AND ?", (account_id, s, e)).fetchone()
            vocab = {"attempts": row["n"], "correct": row["ok"], "dont_know": row["open"]} if row["n"] else None

    ups, downs = [], []
    for ev in events:
        before, after = PROGRESS.get(ev["stage_before"], 0), PROGRESS.get(ev["stage_after"], 0)
        item = {"subject": subject_label(ev["subject"]), "title": ev["title"], "from": ev["stage_before"],
                "to": ev["stage_after"], "label": LABELS.get(ev["stage_after"], ""), "reason": ev["reason"]}
        if after > before:
            ups.append(item)
        elif after < before:
            downs.append(item)
    checks_passed = sum(1 for ev in events if ev["stage_after"] == "gefestigt")

    reliability = day_close.reliability(account_id, today, weeks=2)
    current = reliability.get("current") or {"evenings": 0, "closed": 0, "own": 0}
    previous = next((w for w in reliability.get("weeks", []) if w["week"] == (start - timedelta(days=7)).isoformat()), None)

    material_missing, exams_ahead = [], []
    try:
        from .exams import resolve_exams
        from .sources import photo_requests
        found = (await resolve_exams(account_id, days_ahead=14)).get("exams", [])
        horizon = (today + timedelta(days=14)).isoformat()
        exams_ahead = [{"subject": subject_label(x.get("subject_name") or x.get("title") or ""), "date": (x.get("date") or "")[:10]}
                       for x in found if today.isoformat() <= (x.get("date") or "")[:10] <= horizon]
        material_missing = [{"subject": subject_label(m["subject"]), "exam_date": m["exam_date"], "label": m["label"],
                             "pages_label": m["pages_label"]} for m in photo_requests(account_id, found, today.isoformat())]
    except Exception:
        LOG.debug("Arbeiten oder Materialbedarf für Konto %s nicht lesbar", account_id, exc_info=True)

    photo_days = {a["school_day"] for a in afternoon}
    photos = sum(1 for a in afternoon if a["answer"] == "photo")
    minutes = int(round((units["sec"] or 0) / 60))
    costs_eur = round((cost_micro or 0) / 1e6, 2)

    lines: list[str] = []
    if current["evenings"]:
        lines.append(f"An {current['own']} von {current['evenings']} Abenden vor einem Schultag war vor der Erinnerung alles erledigt"
                     + (f" (Vorwoche {previous['own']} von {previous['evenings']})." if previous and previous.get("evenings") else "."))
    else:
        lines.append("In dieser Woche noch kein Abend vor einem Schultag.")
    if ups:
        shown = ", ".join(f"{u['title']} ({STAGE_WORD[u['to']]})" for u in ups[:3])
        lines.append(f"{len(ups)} {'Thema' if len(ups) == 1 else 'Themen'} eine Stufe weiter: {shown}" + (" …" if len(ups) > 3 else "") + ".")
    if downs:
        shown = ", ".join(f"{d['title']} ({STAGE_WORD[d['to']]})" for d in downs[:3])
        lines.append(f"{len(downs)} {'Thema' if len(downs) == 1 else 'Themen'} zurück: {shown}" + (" …" if len(downs) > 3 else "") + ".")
    if checks_passed:
        lines.append(f"{checks_passed} {'Kurzprüfung' if checks_passed == 1 else 'Kurzprüfungen'} nach Tagen bestanden (gefestigt).")
    if units["n"]:
        lines.append(f"{units['n']} {'Einheit' if units['n'] == 1 else 'Einheiten'} mit dem Mentor, rund {minutes} Minuten, in "
                     + ", ".join(subject_label(x) for x in unit_subjects) + ("." if ups or downs else "; kein Stufenwechsel dabei."))
    else:
        lines.append("Keine Einheit mit dem Mentor in dieser Woche.")
    if vocab:
        # „Weiß ich nicht" deckt die Lösung auf und ist Lernen, kein Irrtum.
        open_ = vocab.get("dont_know") or 0
        lines.append(f"{vocab['attempts']} Vokabelabfragen, {vocab['correct']} davon richtig"
                     + (f", {open_}× „Weiß ich nicht“." if open_ else "."))
    lines.append(f"{homework_done} {'Aufgabe' if homework_done == 1 else 'Aufgaben'} erledigt" + (f", {overdue} überfällig." if overdue else "."))
    if photo_days:
        lines.append(f"An {len(photo_days)} {'Tag' if len(photo_days) == 1 else 'Tagen'} nach der Schule geantwortet, {photos} {'Foto' if photos == 1 else 'Fotos'}.")
    for m in material_missing[:3]:
        lines.append(f"Für {m['subject']} am {_short(m['exam_date'])} fehlt noch: {m['label']} {m['pages_label']}".rstrip() + ".")
    for x in exams_ahead[:3]:
        if not any(m["subject"] == x["subject"] for m in material_missing):
            lines.append(f"{x['subject']} am {_short(x['date'])}: Material liegt vor.")
    lines.append(f"KI-Kosten diese Woche: {costs_eur:.2f} € (Anrechnung, keine Rechnung).")

    return {
        "week": {"start": s, "end": e, "label": f"{start.strftime('%d.%m.')} bis {end.strftime('%d.%m.')}"},
        "evenings": {"current": current, "previous": previous},
        "stages": {"ups": ups, "downs": downs, "checks_passed": checks_passed},
        "units": {"count": units["n"], "minutes": minutes, "subjects": [subject_label(x) for x in unit_subjects]},
        "vocab": vocab,
        "homework": {"done": homework_done, "overdue": overdue},
        "afternoon": {"days": len(photo_days), "photos": photos},
        "material_missing": material_missing,
        "exams_ahead": exams_ahead,
        "costs_eur": costs_eur,
        "lines": lines,
    }
