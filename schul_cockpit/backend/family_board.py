"""Die Startseite der Eltern (D166): je Kind auf einen Blick, ob es alles im
Griff hat, was gerade offen ist und wo sich bei den Arbeiten etwas abzeichnet.

Die Seite „Heute“ des Kindes wird nicht wiederholt. Jeder Baustein nennt nur
den Stand und führt mit einem Tipp in den passenden Abschnitt beim Kind.
Drei Stufen, feste Regeln, kein Modellaufruf:

- Eingreifen: eine Aufgabe ist überfällig, oder für eine Arbeit in den
  nächsten 7 Tagen fehlt Material.
- Nachsteuern: etwas ist offen, das jetzt dran wäre, ein Foto muss neu
  gemacht werden, oder eine Arbeit steht in 14 Tagen an und von ihren Themen
  ist noch keines geübt.
- Im Griff: sonst.

Was für morgen ansteht, ist vor dem Abend noch kein Versäumnis: Es steht
neutral da und zählt erst ab der Erinnerungszeit des Kindes. Die Tasche folgt
dem Schultag: vor dem Unterricht die für heute, währenddessen keine, danach
die für den nächsten Schultag (`bag_target()`).
"""
from __future__ import annotations

import logging
import re
from contextlib import closing
from datetime import date, datetime, timedelta

from . import lernstand, usage_report
from .courses import hidden_keys, lesson_is_hidden
from .db import history_conn, webapp_conn
from .queries import lessons_for_date
from .subject_names import label as subject_label

_LOG = logging.getLogger(__name__)

NEAR_DAYS = 21        # bis hierhin eine eigene Zeile mit Balken
LATER_DAYS = 90       # danach nur noch als „Später“
LATER_MAX = 5
URGENT_DAYS = 7       # fehlt dann noch Material: Eingreifen
IDLE_DAYS = 14        # ist dann noch nichts geübt: Nachsteuern
FEEDBACK_DAYS = 7
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
LEVELS = {"bad": "Eingreifen", "warn": "Nachsteuern", "good": "Im Griff"}
_KINDS = [("vergleichsarbeit", "Vergleichsarbeit"), ("sprechprüfung", "Sprechprüfung"),
          ("lernkontrolle", "Lernkontrolle"), ("vokabeltest", "Vokabeltest"), ("test", "Test")]


def go(page: str, *args, section: str | None = None) -> dict:
    """Ein Schnellzugriff: Seite des Kindes, Argumente, Abschnitt darauf."""
    return {"page": page, "args": [str(a) for a in args], "section": section}


def day_label(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m.')}"


def exam_kind(title: str | None) -> str:
    low = (title or "").casefold()
    for word, kind in _KINDS:
        if re.search(rf"\b{word}", low):
            return kind
    return "Arbeit"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _ended(lesson: dict, now: datetime) -> bool:
    end = lesson.get("end_time")
    if not isinstance(end, int) or not 0 <= end <= 2359 or end % 100 > 59:
        return False
    return now.time() >= datetime.strptime(f"{end:04d}", "%H%M").time()


def next_school_day(account_id: int, today: date) -> str | None:
    hidden = hidden_keys(account_id)
    with closing(history_conn()) as conn:
        for offset in range(1, 8):
            day = (today + timedelta(days=offset)).isoformat()
            # Ein Tag, an dem alles ausfällt, ist kein Schultag.
            if any(not lesson_is_hidden(l, hidden) and not l.get("is_cancelled") and not l.get("was_absent")
                   for l in lessons_for_date(conn, account_id, day)):
                return day
    return None


def _clock(value) -> int | None:
    return value if isinstance(value, int) and 0 <= value <= 2359 and value % 100 <= 59 else None


def bag_target(account_id: int, today: date, now: datetime) -> tuple[str | None, str]:
    """Welche Tasche jetzt zählt. Vor dem Unterricht die für heute, gepackt am
    Vorabend; während der Schulzeit keine, dann lässt sich nicht packen; nach
    Schulschluss und an freien Tagen die für den nächsten Schultag, auch am
    Freitag schon für Montag."""
    hidden = hidden_keys(account_id)
    with closing(history_conn()) as conn:
        held = [l for l in lessons_for_date(conn, account_id, today.isoformat())
                if not lesson_is_hidden(l, hidden) and not l.get("is_cancelled") and not l.get("was_absent")]
    starts = [t for t in (_clock(l.get("start_time")) for l in held) if t is not None]
    ends = [t for t in (_clock(l.get("end_time")) for l in held) if t is not None]
    if starts and ends:
        clock = now.hour * 100 + now.minute
        if clock < min(starts):
            return today.isoformat(), "before"
        if clock < max(ends):
            return None, "school"
    return next_school_day(account_id, today), "after"


def feedback(account_id: int, today: date, now: datetime) -> dict:
    """Stunden ohne Rückmeldung: die der letzten Tage und die schon beendeten
    von heute. Ausgefallene, versäumte und ausgeblendete Stunden zählen nicht."""
    hidden = hidden_keys(account_id)
    horizon = (today - timedelta(days=FEEDBACK_DAYS)).isoformat()
    with closing(history_conn()) as hconn:
        rows = [dict(r) for r in hconn.execute(
            "SELECT * FROM lessons WHERE account_id=? AND date>=? AND date<=? "
            "AND (code IS NULL OR LOWER(code)!='cancelled') AND was_absent=0",
            (account_id, horizon, today.isoformat()))]
    lessons = [l for l in rows if not lesson_is_hidden(l, hidden)
               and (l["date"] < today.isoformat() or _ended(l, now))]
    if not lessons:
        return {"earlier": 0, "today": 0, "today_total": 0, "total": 0}
    ids = [l["id"] for l in lessons]
    with closing(webapp_conn()) as wconn:
        rated = {r[0] for r in wconn.execute(
            f"SELECT DISTINCT lesson_id FROM lesson_checkins WHERE account_id=? AND rating IS NOT NULL "
            f"AND lesson_id IN ({','.join('?' * len(ids))})", (account_id, *ids))}
    today_lessons = [l for l in lessons if l["date"] == today.isoformat()]
    return {"earlier": sum(1 for l in lessons if l["date"] < today.isoformat() and l["id"] not in rated),
            "today": sum(1 for l in today_lessons if l["id"] not in rated),
            "today_total": len(today_lessons), "total": len(lessons)}


def acute(account_id: int, tasks: list[dict], today: date, now: datetime, evening: bool) -> tuple[list[dict], list[str]]:
    """Was jetzt offen ist, als Zeilen, und was schon erledigt ist, als eine Zeile."""
    rows, ok = [], []
    today_iso, tomorrow = today.isoformat(), (today + timedelta(days=1)).isoformat()
    overdue = [t for t in tasks if t["due_date"] and t["due_date"] < today_iso]
    due_today = [t for t in tasks if t["due_date"] == today_iso]
    due_tomorrow = [t for t in tasks if t["due_date"] == tomorrow]
    undated = [t for t in tasks if not t["due_date"]]

    def names(items):
        return " · ".join(t["title"] for t in items[:3]) + (" …" if len(items) > 3 else "")

    if overdue:
        rows.append({"key": "overdue", "tone": "bad", "icon": "⚠️",
                     "title": f"{_plural(len(overdue), 'Aufgabe', 'Aufgaben')} überfällig",
                     "detail": names(overdue), "go": go("today", section="aufgaben")})
    if due_today or due_tomorrow:
        both = due_today + due_tomorrow
        rows.append({"key": "due", "tone": "warn" if due_today or evening else "info", "icon": "📝",
                     "title": f"{_plural(len(both), 'Aufgabe', 'Aufgaben')} bis morgen offen",
                     "detail": names(both), "go": go("today", section="aufgaben")})
    elif not overdue:
        ok.append("Aufgaben bis morgen erledigt")
    if undated:
        rows.append({"key": "undated", "tone": "info", "icon": "🗂️",
                     "title": f"{_plural(len(undated), 'Aufgabe', 'Aufgaben')} ohne Termin",
                     "detail": "bitte einordnen", "go": go("today", section="ohne-termin")})

    day, phase = bag_target(account_id, today, now)
    if day:
        try:
            from .packing import packing_plan, view
            items, fingerprint, schedule = packing_plan(account_id, date.fromisoformat(day))
            with closing(webapp_conn()) as conn:
                bag = view(account_id, date.fromisoformat(day), items, fingerprint, conn, schedule)
        except Exception:
            _LOG.warning("Packliste für Konto %s nicht lesbar", account_id, exc_info=True)
            bag = None
        # Vor dem Unterricht fehlt wirklich etwas. Die Tasche für den nächsten
        # Schultag mahnt erst am Abend direkt davor; am Freitag steht die für
        # Montag schon da, aber neutral.
        before = phase == "before"
        urgent = before or (evening and day == tomorrow)
        name = "heute" if before else day_label(day)
        if bag and bag["items"] and bag["confirmed_count"] < len(bag["items"]):
            rows.append({"key": "bag", "tone": "warn" if urgent else "info", "icon": "🎒",
                         "title": f"Tasche für {name}: {bag['confirmed_count']} von {len(bag['items'])} Fächern",
                         "detail": "noch nicht alles abgehakt", "go": go("today", section="tasche")})
        elif bag and bag["items"]:
            ok.append(f"Tasche für {'heute' if before else day_label(day)[:2]} gepackt")

    fb = feedback(account_id, today, now)
    if fb["earlier"] or fb["today"]:
        parts = ([f"heute {fb['today']}"] if fb["today"] else []) + ([f"an den Vortagen {fb['earlier']}"] if fb["earlier"] else [])
        rows.append({"key": "feedback", "tone": "warn" if fb["earlier"] or evening else "info", "icon": "🗣️",
                     "title": f"{_plural(fb['today'] + fb['earlier'], 'Stunde', 'Stunden')} ohne Rückmeldung",
                     "detail": ", ".join(parts),
                     "go": go("today", section="rueckmelden") if fb["today"] else go("week")})
    elif fb["today_total"]:
        ok.append(f"{fb['today_total']}/{fb['today_total']} Stunden bewertet")

    try:
        from . import materials as store
        retakes = store.retakes(account_id)
    except Exception:
        retakes = []
    if retakes:
        rows.append({"key": "retake", "tone": "warn", "icon": "📷",
                     "title": f"{_plural(len(retakes), 'Seite', 'Seiten')} neu fotografieren",
                     "detail": " · ".join(f"„{r['title']}“" for r in retakes[:2]) + f" · {retakes[0]['reason']}",
                     "go": go("materialien", section="fotos")})
    return rows, ok


def exam_rows(account_id: int, upcoming: list[dict], entries: list[dict], today: date) -> tuple[list[dict], list[dict]]:
    """Die Arbeiten chronologisch: nahe mit Balken, spätere als eine Zeile."""
    from .routers.exams import exam_scope, scope_start
    from . import sources
    near, later = [], []
    for e in sorted(upcoming, key=lambda x: x["date"]):
        days = (date.fromisoformat(e["date"]) - today).days
        if days > LATER_DAYS or (days > NEAR_DAYS and len(later) >= LATER_MAX):
            continue
        subject, key = e.get("subject_name"), e.get("exam_key")
        since = scope_start(subject, e["date"], entries)
        try:
            topics = [t for t in lernstand.topics_for(account_id, key, subject, with_material=False) if not t.get("stale")]
            if not topics and days <= NEAR_DAYS:
                # Ohne Themenliste die aus dem Unterricht erschlossenen Themen,
                # wie auf der Klausurseite; ohne Modellaufruf.
                lernstand.ensure_assumed_topics(account_id, key, subject, exam_scope(account_id, subject, since, e["date"]))
                topics = [t for t in lernstand.topics_for(account_id, key, subject, with_material=False) if not t.get("stale")]
        except Exception:
            _LOG.warning("Themen der Arbeit in %s nicht lesbar", subject, exc_info=True)
            topics = []
        try:
            src = sources.exam_sources(account_id, subject, since, e["date"])
        except Exception:
            _LOG.warning("Quellenstand der Arbeit in %s nicht lesbar", subject, exc_info=True)
            src = None
        counts = lernstand.stage_counts(topics)
        stages = {"sitzt": counts.get("sitzt", 0) + counts.get("gefestigt", 0), "wackelt": counts.get("wackelt", 0),
                  "angefangen": counts.get("angefangen", 0), "neu": counts.get("neu", 0)}
        missing = (src or {}).get("missing") or 0
        row = {"exam_key": key, "date": e["date"], "day": day_label(e["date"]), "days_until": days,
               "subject_name": subject, "kind": exam_kind(e.get("title")), "topics": len(topics),
               "practiced": len(topics) - stages["neu"], "stages": stages, "missing": missing,
               "material_ok": bool(src) and not missing and not (src or {}).get("pending"),
               "go": go("klausuren", section=f"arbeit-{key}")}
        (near if days <= NEAR_DAYS else later).append(row)
    return near, later


def watch(account_id: int, support: list[dict], today: date) -> list[dict]:
    """Was sich über Wochen abzeichnet. Spät in der App zählt nur auf der
    Anmeldung des Kindes; das Elterngerät sagt über das Kind nichts."""
    rows = [{"key": f"hard-{s['subject_id']}", "tone": "warn", "icon": "∿",
             "title": f"{subject_label(s['subject_name'] or s['subject_short'] or '')} fällt schwer",
             "detail": f"{s['hard_count']} von {s['total_count']} bewerteten Stunden der letzten 3 Wochen als schwer bewertet",
             "subject_name": s["subject_name"], "go": go("subject", s["subject_id"])} for s in support]
    try:
        late = usage_report.week(account_id, today).get("late") or []
    except Exception:
        _LOG.warning("Nutzungsbericht für Konto %s nicht lesbar", account_id, exc_info=True)
        late = []
    if late:
        rows.append({"key": "late", "tone": "warn", "icon": "☾", "title": "Spät auf dem eigenen Gerät",
                     "detail": "; ".join(f"{d['day']} {', '.join(d['times'][:3])}" for d in late[:3]), "go": None})
    return rows


def level(acute_rows: list[dict], near: list[dict]) -> dict:
    reasons = []
    if any(r["tone"] == "bad" for r in acute_rows):
        reasons.append(("bad", "Aufgaben überfällig"))
    for x in near:
        if x["days_until"] <= URGENT_DAYS and x["missing"]:
            reasons.append(("bad", f"Material für {subject_label(x['subject_name'] or '')} fehlt"))
    reasons += [("warn", r["title"]) for r in acute_rows if r["tone"] == "warn"]
    for x in near:
        if x["days_until"] <= IDLE_DAYS and x["topics"] and not x["practiced"]:
            reasons.append(("warn", f"{subject_label(x['subject_name'] or '')}: noch nichts geübt"))
    worst = "bad" if any(r[0] == "bad" for r in reasons) else "warn" if reasons else "good"
    return {"level": worst, "label": LEVELS[worst], "reasons": [r[1] for r in reasons]}


def board(account_id: int, tasks: list[dict], upcoming: list[dict], entries: list[dict],
          support: list[dict], today: date, now: datetime, evening_from: str) -> dict:
    evening = now.strftime("%H:%M") >= evening_from
    rows, ok = acute(account_id, tasks, today, now, evening)
    near, later = exam_rows(account_id, upcoming, entries, today)
    return {"status": level(rows, near), "acute": rows, "ok": ok, "evening": evening,
            "exams": near, "later": later, "watch": watch(account_id, support, today)}
