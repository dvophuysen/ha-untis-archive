"""Die Woche rollend (D184): die nächsten fünf Schultage statt einer
Kalenderwoche, in einem Aufruf.

Schultag ist ein Tag mit sichtbaren Stunden im Stundenplan; ein Tag, an dem
alles ausfällt, bleibt als „fällt ganz aus“ stehen (wie D170). Über den
bekannten Stundenplan hinaus gilt Montag bis Freitag als Annahme, Ferien und
Feiertage aus UNTIS (`master_holidays`) ausgenommen, soweit sie vorliegen.

Standard ist heute, wenn heute Unterricht war, sonst der nächste Schultag.
Ist die Schule heute schon vorbei, zählen die fünf Tage ab dem nächsten
Schultag, heute bleibt oben stehen. Geblättert wird um fünf Schultage.

Je Tag: die Leiste der Familienkarte (`family_board.schedule_day`, dieselbe
Ableitung für früher Schluss und späteren Beginn), die Stunden mit
Rückmeldung, fällige Hausaufgaben und Arbeiten mit Lernstand
(`practice.raster`). Für vergangene Zeiträume ein kindgerechter Rückblick
ohne Kosten und KI-Daten. Kein Modellaufruf; der Arbeitenkalender kommt aus
gespeicherten Terminen und ist mit einer Frist abgesichert.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta

from . import family_board
from .courses import hidden_keys, lesson_is_hidden
from .db import history_conn, webapp_conn
from .lernstand import PROGRESS
from .queries import lessons_in_range
from .subject_names import label as subject_label

LOG = logging.getLogger("schul_cockpit.week_rolling")

DAYS = 5
LOOKAHEAD = 100      # Sommerferien plus Puffer
LOOKBACK = 70
FEEDBACK_DAYS = 7    # wie die Familienkarte: ältere Rückmeldungen führen hierher
EXAM_TIMEOUT = 4.0


def holidays(account_id: int, start: date, end: date) -> list[dict]:
    """Ferien und Feiertage aus UNTIS, falls die Integration sie liefert."""
    try:
        with closing(history_conn()) as conn:
            rows = conn.execute(
                "SELECT name, longName, startDate, endDate FROM master_holidays "
                "WHERE account_id=? AND startDate<=? AND endDate>=? ORDER BY startDate",
                (account_id, end.isoformat(), start.isoformat())).fetchall()
    except sqlite3.Error:
        return []
    return [{"name": r["longName"] or r["name"] or "Ferien", "start": r["startDate"], "end": r["endDate"]}
            for r in rows if r["startDate"] and r["endDate"]]


def _holiday_on(hols: list[dict], day: str) -> dict | None:
    return next((h for h in hols if h["start"] <= day <= h["end"]), None)


def _known_range(account_id: int) -> tuple[str | None, str | None]:
    with closing(history_conn()) as conn:
        row = conn.execute("SELECT MIN(date), MAX(date) FROM lessons WHERE account_id=?", (account_id,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def _visible(account_id: int, start: date, end: date) -> dict[str, list[dict]]:
    hidden = hidden_keys(account_id)
    with closing(history_conn()) as conn:
        rows = lessons_in_range(conn, account_id, start.isoformat(), end.isoformat())
    by_day: dict[str, list[dict]] = {}
    for l in rows:
        if not lesson_is_hidden(l, hidden):
            by_day.setdefault(l["date"], []).append(l)
    return by_day


def _school_over(lessons: list[dict], now: datetime) -> bool:
    ends = [l["end_time"] for l in lessons if not l.get("is_cancelled") and isinstance(l.get("end_time"), int)]
    return not ends or now.hour * 100 + now.minute >= max(ends)


def pick_days(account_id: int, today: date, now: datetime, *, start: date | None = None,
              before: date | None = None, count: int = DAYS) -> dict:
    """Welche Tage gezeigt werden, mit ihren Stunden und den freien Werktagen
    dazwischen. Ohne `start` und `before` die Standardansicht ab heute."""
    first_known, last_known = _known_range(account_id)
    if before:
        lo, hi = before - timedelta(days=LOOKBACK), before - timedelta(days=1)
    else:
        lo = start or today
        hi = lo + timedelta(days=LOOKAHEAD)
    by_day = _visible(account_id, lo, hi)
    hols = holidays(account_id, lo, hi)

    def school(day: date) -> bool:
        iso = day.isoformat()
        if by_day.get(iso):
            return True
        # Hinter dem bekannten Stundenplan: Montag bis Freitag als Annahme.
        return (day.weekday() < 5 and last_known is not None and iso > last_known
                and not _holiday_on(hols, iso))

    days: list[date] = []
    extra_today = False
    if before:
        cursor = hi
        while cursor >= lo and len(days) < count:
            if first_known and cursor.isoformat() < first_known:
                break
            if school(cursor):
                days.append(cursor)
            cursor -= timedelta(days=1)
        days.reverse()
    else:
        cursor = lo
        if start is None and by_day.get(today.isoformat()) and _school_over(by_day[today.isoformat()], now):
            # Schule heute vorbei: heute bleibt oben, gezählt wird ab morgen.
            days.append(today)
            extra_today = True
            cursor = today + timedelta(days=1)
        while cursor <= hi and len(days) < count + extra_today:
            if school(cursor):
                days.append(cursor)
            cursor += timedelta(days=1)

    # Freie Werktage im gezeigten Zeitraum und, bei der Standardansicht in den
    # Ferien, zwischen heute und dem ersten Schultag.
    free: list[dict] = []
    if days:
        span_start = min(days[0], today) if not before and not start else days[0]
        cursor = span_start
        while cursor <= days[-1]:
            iso = cursor.isoformat()
            if cursor.weekday() < 5 and cursor not in days and (not first_known or iso >= first_known):
                hol = _holiday_on(hols, iso)
                free.append({"date": iso, "name": hol["name"] if hol else None,
                             "holiday_end": hol["end"] if hol else None})
            cursor += timedelta(days=1)
    return {"days": [d.isoformat() for d in days], "by_day": by_day, "free": free,
            "extra_today": extra_today, "holidays": hols, "first_known": first_known}


def free_ranges(free: list[dict]) -> list[dict]:
    """Aufeinanderfolgende freie Werktage mit gleichem Namen als ein Eintrag."""
    out: list[dict] = []
    for f in free:
        d = date.fromisoformat(f["date"])
        prev = out[-1] if out else None
        if prev and prev["name"] == f["name"]:
            gap = (d - date.fromisoformat(prev["end"])).days
            # Wochenende dazwischen zählt nicht als Lücke.
            if gap == 1 or (gap <= 3 and d.weekday() == 0):
                prev["end"] = f["date"]
                continue
        out.append({"start": f["date"], "end": f["date"], "name": f["name"], "holiday_end": f["holiday_end"]})
    for r in out:
        r["label"] = (family_board.day_label(r["start"]) if r["start"] == r["end"]
                      else f"{family_board.day_label(r['start'])} – {family_board.day_label(r['end'])}")
    return out


def annotate(account_id: int, lessons: list[dict]) -> None:
    """Rückmeldung und Nachgeholt je Stunde, wie in der Wochenansicht."""
    ids = [l["id"] for l in lessons]
    checkins: dict[int, dict] = {}
    caught: set[int] = set()
    if ids:
        marks = ",".join("?" * len(ids))
        with closing(webapp_conn()) as c:
            for r in c.execute(f"SELECT lesson_id, rating, note FROM lesson_checkins "
                               f"WHERE account_id=? AND lesson_id IN ({marks})", (account_id, *ids)):
                checkins[r["lesson_id"]] = {"rating": r["rating"], "note": r["note"]}
            caught = {r[0] for r in c.execute(f"SELECT lesson_id FROM caught_up "
                                              f"WHERE account_id=? AND lesson_id IN ({marks})", (account_id, *ids))}
    try:
        from . import sources
        sources.annotate_lessons(account_id, lessons)
    except Exception:
        LOG.debug("Quellen der Stunden nicht lesbar", exc_info=True)
    for l in lessons:
        ck = checkins.get(l["id"])
        l["rating"] = ck["rating"] if ck else None
        l["checkin"] = ck
        l["caught_up"] = l["id"] in caught


def _ended(lesson: dict, day: str, today: date, now: datetime) -> bool:
    if day < today.isoformat():
        return True
    if day > today.isoformat():
        return False
    end = lesson.get("end_time")
    return isinstance(end, int) and now.hour * 100 + now.minute >= end


def _unrated(lessons: list[dict], day: str, today: date, now: datetime) -> list[dict]:
    return [l for l in lessons if not l.get("is_cancelled") and not l.get("was_absent")
            and _ended(l, day, today, now) and not (l.get("checkin") or {}).get("rating")]


async def exams_between(account_id: int, first: date, last: date, today: date) -> list[dict]:
    """Termine aus dem Arbeitenkalender und selbst eingetragene, mit Frist."""
    try:
        from .exams import resolve_exams
        ahead = max(0, (last - today).days)
        past = max(0, (today - first).days)
        data = await asyncio.wait_for(resolve_exams(account_id, days_ahead=ahead, past_days=past),
                                      timeout=EXAM_TIMEOUT)
    except Exception:
        LOG.info("Arbeitenkalender für Konto %s nicht rechtzeitig lesbar", account_id, exc_info=True)
        return []
    lo, hi = first.isoformat(), last.isoformat()
    return [e for e in data.get("exams", []) if lo <= (e.get("date") or "")[:10] <= hi]


def _readiness(account_id: int, exam_key: str | None) -> tuple[int, int]:
    if not exam_key:
        return 0, 0
    try:
        from . import practice
        r = practice.raster(account_id, exam_key)
        return r["ready"], r["total"]
    except Exception:
        LOG.debug("Lernstand der Arbeit %s nicht lesbar", exam_key, exc_info=True)
        return 0, 0


def _tasks(account_id: int, first: str, last: str) -> list[dict]:
    with closing(webapp_conn()) as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id, title, subject_name, status, due_date, due_time, task_type FROM tasks "
            "WHERE account_id=? AND due_date BETWEEN ? AND ? AND status!='skipped' "
            "ORDER BY due_date, (due_time IS NULL), due_time, id", (account_id, first, last))]
    for t in rows:
        t["subject"] = subject_label(t["subject_name"] or "") if t["subject_name"] else ""
        t["done"] = t["status"] == "done"
    return rows


def review(account_id: int, first: str, last: str, lessons: list[dict]) -> dict:
    """Rückblick für Kinder: was geschafft wurde, ohne Kosten und KI-Daten."""
    held = [l for l in lessons if not l.get("is_cancelled") and not l.get("was_absent")]
    rated = sum(1 for l in held if (l.get("checkin") or {}).get("rating"))
    with closing(webapp_conn()) as c:
        # completed_at ist UTC; gezählt wird der deutsche Erledigt-Tag.
        from .week_review import done_between
        homework = done_between(c, account_id, first, last)
        vocab = {"attempts": 0, "correct": 0}
        try:
            row = c.execute("SELECT COUNT(*), COALESCE(SUM(result='correct'),0) FROM vocab_attempts "
                            "WHERE account_id=? AND substr(created_at,1,10) BETWEEN ? AND ?",
                            (account_id, first, last)).fetchone()
            vocab = {"attempts": row[0], "correct": row[1]}
        except sqlite3.Error:
            pass
        sure: list[dict] = []
        try:
            for r in c.execute(
                    "SELECT e.stage_before, e.stage_after, t.title, t.subject FROM topic_events e "
                    "JOIN exam_topics t ON t.id=e.topic_id WHERE e.account_id=? "
                    "AND substr(e.created_at,1,10) BETWEEN ? AND ? ORDER BY e.created_at", (account_id, first, last)):
                before, after = PROGRESS.get(r["stage_before"], 0), PROGRESS.get(r["stage_after"], 0)
                if after >= PROGRESS["sitzt"] > before and not any(s["title"] == r["title"] for s in sure):
                    sure.append({"title": r["title"], "subject": subject_label(r["subject"] or "")})
        except sqlite3.Error:
            pass
    lines = []
    if homework:
        lines.append(f"{homework} {'Hausaufgabe' if homework == 1 else 'Hausaufgaben'} erledigt")
    if vocab["attempts"]:
        lines.append(f"{vocab['attempts']} Vokabeln geübt, {vocab['correct']} richtig")
    if sure:
        shown = ", ".join(s["title"] for s in sure[:3]) + (" …" if len(sure) > 3 else "")
        lines.append(f"{len(sure)} {'Thema sitzt' if len(sure) == 1 else 'Themen sitzen'} jetzt: {shown}")
    if held:
        lines.append(f"{rated} von {len(held)} Stunden zurückgemeldet")
    return {"homework_done": homework, "vocab": vocab, "topics_sure": sure,
            "lessons": {"held": len(held), "rated": rated}, "lines": lines}


async def rolling(account_id: int, today: date, now: datetime, *, start: date | None = None,
                  before: date | None = None, count: int = DAYS) -> dict:
    picked = pick_days(account_id, today, now, start=start, before=before, count=count)
    day_list = picked["days"]
    today_iso = today.isoformat()
    base = {"today": today_iso, "default": start is None and before is None,
            "free": free_ranges(picked["free"]), "days": [], "feedback": {"count": 0, "days": []}}
    if not day_list:
        # Weder Stundenplan noch Annahme: Ferien ohne bekannten Anschluss.
        hol = _holiday_on(picked["holidays"], today_iso)
        return {**base, "mode": "empty", "range": None,
                "holiday": {"name": hol["name"], "end": hol["end"]} if hol else None,
                "prev_before": None, "next_from": None, "review": None}

    first, last = date.fromisoformat(day_list[0]), date.fromisoformat(day_list[-1])
    lessons_all = [l for d in day_list for l in picked["by_day"].get(d, [])]
    annotate(account_id, lessons_all)

    cal = await exams_between(account_id, first, last, today)
    exams_by_day: dict[str, list[dict]] = {}
    for e in cal:
        d = e["date"][:10]
        ready, total = _readiness(account_id, e.get("exam_key"))
        exams_by_day.setdefault(d, []).append({
            "exam_key": e.get("exam_key"), "subject": subject_label(e.get("subject_name") or e.get("title") or ""),
            "kind": family_board.exam_kind(e.get("title")), "ready": ready, "total": total})
    # Vokabeltests aus Hausaufgaben sind Termine wie Arbeiten (D187, D190).
    try:
        from . import vocab_pensum
        for t in vocab_pensum._homework_tests(account_id, today):
            d = t["date"].isoformat()
            if first <= t["date"] <= last:
                exams_by_day.setdefault(d, []).append({
                    "exam_key": t["exam_key"], "subject": subject_label(t["subject"]),
                    "kind": family_board.exam_kind("Vokabeltest"), "ready": 0, "total": 0,
                    "title": f"Vokabeltest {t['unit'][1] if t['unit'] else t['unit_ref']}"})
    except Exception:
        pass
    tasks = _tasks(account_id, day_list[0], day_list[-1])

    days = []
    for d in day_list:
        lessons = picked["by_day"].get(d, [])
        exams = exams_by_day.get(d, [])
        covered = {x["subject"].casefold() for x in exams}
        # Arbeiten, die nur UNTIS kennt, ohne Eintrag im Arbeitenkalender.
        for l in lessons:
            subj = subject_label(l.get("subject_name") or l.get("subject_short") or "")
            if l.get("exam") and not l.get("is_cancelled") and subj.casefold() not in covered:
                covered.add(subj.casefold())
                exams.append({"exam_key": None, "subject": subj,
                              "kind": family_board.exam_kind((l["exam"] or {}).get("name")), "ready": 0, "total": 0})
        strip = family_board.schedule_day(d, lessons, today, now, covered) if lessons else None
        for l in lessons:
            # Dieselbe Markierung wie in der Leiste, fürs Raster je Stunde.
            l["exam_marked"] = bool(l.get("exam")) or (not l.get("is_cancelled") and subject_label(
                l.get("subject_name") or l.get("subject_short") or "").casefold() in covered)
        day_tasks = [t for t in tasks if t["due_date"] == d]
        hol = _holiday_on(picked["holidays"], d)
        days.append({
            "date": d, "label": family_board.day_label(d), "is_today": d == today_iso, "is_past": d < today_iso,
            "assumed": not lessons, "week": date.fromisoformat(d).isocalendar()[1],
            "holiday": hol["name"] if hol else None,
            "strip": strip, "lessons": lessons, "exams": exams, "tasks": day_tasks,
            "tasks_open": sum(1 for t in day_tasks if not t["done"]),
        })

    mode = "past" if last < today else "ahead"
    fb_days = []
    if mode == "past":
        for day in days:
            rows = _unrated(day["lessons"], day["date"], today, now)
            if rows:
                fb_days.append({"date": day["date"], "label": day["label"], "lessons": rows})
    else:
        # Ältere Stunden ohne Rückmeldung: Die Familienkarte führt hierher.
        lo = today - timedelta(days=FEEDBACK_DAYS)
        earlier = _visible(account_id, lo, today - timedelta(days=1))
        flat = [l for ls in earlier.values() for l in ls]
        if flat:
            annotate(account_id, flat)
        for d in sorted(earlier):
            rows = _unrated(earlier[d], d, today, now)
            if rows:
                fb_days.append({"date": d, "label": family_board.day_label(d), "lessons": rows})
    feedback = {"count": sum(len(x["lessons"]) for x in fb_days), "days": fb_days}

    return {**base, "mode": mode, "days": days, "feedback": feedback, "holiday": None,
            "range": {"start": day_list[0], "end": day_list[-1]},
            # Zurück nur, solange der Stundenplan weiter zurückreicht.
            "prev_before": day_list[0] if picked["first_known"] and picked["first_known"] < day_list[0] else None,
            "next_from": (last + timedelta(days=1)).isoformat(),
            "review": review(account_id, day_list[0], day_list[-1], lessons_all) if mode == "past" else None}
