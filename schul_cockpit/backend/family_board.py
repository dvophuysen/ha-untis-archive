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
from datetime import date, datetime, timedelta, timezone

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
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
LEVELS = {"bad": "Eingreifen", "warn": "Nachsteuern", "good": "Im Griff"}
_KINDS = [("vergleichsarbeit", "Vergleichsarbeit"), ("sprechprüfung", "Sprechprüfung"),
          ("lernkontrolle", "Lernkontrolle"), ("vokabeltest", "Vokabeltest"), ("test", "Test")]


def go(page: str, *args, section: str | None = None, parent: bool = False) -> dict:
    """Ein Schnellzugriff: Seite des Kindes, Argumente, Abschnitt darauf.

    Ohne ``parent`` öffnet die Startseite die Seite des Kindes zum Mitlesen
    (D175). Was ein Elternteil selbst tun muss, führt mit ``parent`` in die
    Elternansicht unter „Erledigen“ (D183): Im Mitlesen scheiterte es sonst."""
    target = {"page": page, "args": [str(a) for a in args], "section": section}
    if parent:
        target["parent"] = True
    return target


def day_label(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{WEEKDAYS[d.weekday()]} {d.strftime('%d.%m.')}"


def exam_kind(title: str | None) -> str:
    low = (title or "").casefold()
    for word, kind in _KINDS:
        if re.search(rf"\b{word}", low):
            return kind
    return "Arbeit"


def _where(material: dict) -> str:
    """Heft und Seite, wenn bekannt („Grammatikheft S. 24“), sonst der Titel."""
    if material.get("source_page"):
        return f"{material.get('source_label') or 'Buch'} S. {material['source_page']}"
    return f"„{material.get('title') or 'Ohne Titel'}“"


def _brief(text: str, limit: int = 60) -> str:
    """Ein Grund in Kurzform: bis zum ersten Semikolon, höchstens eine Zeile.
    Der volle Wortlaut steht in den Materialien."""
    head = (text or "").split(";")[0].strip()
    return head if len(head) <= limit else head[:limit].rsplit(" ", 1)[0] + " …"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


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
    """Stunden ohne Rückmeldung nach derselben Regel wie Ring, Serie und
    Tagesabschluss (``rewards.feedback_due``, D210): die vergessenen der
    Vortage seit ``rewards.FEEDBACK_FROM`` und die schon beendeten von heute.
    Ausgefallene, versäumte, ausgeblendete, erlassene Stunden und Einträge
    ohne Fach zählen nicht, Teamunterricht zählt einmal."""
    from .rewards import feedback_due
    today_iso = today.isoformat()
    due = feedback_due(account_id, today, now)
    todays = [done for slot, done in due if slot[0]["date"] == today_iso]
    return {"earlier": sum(1 for slot, done in due if not done and slot[0]["date"] < today_iso),
            "today": todays.count(False), "today_total": len(todays), "total": len(due)}


def _merged(lessons: list[dict]) -> list[list[dict]]:
    """Doppelstunden als eine Zeile, wie auf „Heute“ (dayPhase.mergeLessons):
    gleiches Fach, gleicher Zustand, höchstens 20 Minuten dazwischen.
    Teamunterricht (``rewards.same_slot``) steht mit in der Zeile."""
    from .rewards import feedback_slots
    groups: list[list[dict]] = []
    for slot in feedback_slots(sorted(lessons, key=lambda x: x.get("start_time") or 0)):
        l = slot[0]
        last = groups[-1][-1] if groups else None
        if last is not None:
            gap = (_minutes(l.get("start_time")) or 0) - (_minutes(last.get("end_time")) or 0)
            same = (l.get("subject_name") or l.get("subject_short")) == (last.get("subject_name") or last.get("subject_short"))
            if same and bool(l.get("is_cancelled")) == bool(last.get("is_cancelled")) and 0 <= gap <= 20:
                groups[-1].extend(slot)
                continue
        groups.append(list(slot))
    return groups


def _group_open(group: list[dict], done: set) -> bool:
    """Eine Zeile ist offen, solange eine ihrer Stunden keine Rückmeldung hat;
    bei Teamunterricht genügt die zu einem der Einträge."""
    from .rewards import feedback_slots
    return any(not any(l["id"] in done for l in slot) for slot in feedback_slots(group))


def _minutes(hhmm) -> int | None:
    return hhmm // 100 * 60 + hhmm % 100 if isinstance(hhmm, int) else None


def rings(account_id: int, today: date, now: datetime) -> dict:
    """Die vier Ringe von „Heute“ für die Familienkarte, nach denselben Regeln:
    Aufgaben bis zum nächsten Schultag samt Überfälligem, die Lernliste (am
    Wochenende die vom Freitag, D205), die Tasche, die jetzt zählt, und die
    Rückmeldungen zu den beendeten Stunden von heute (Doppelstunde einmal).
    Liest nur; für Eltern wird nichts festgehalten."""
    today_iso = today.isoformat()
    nxt = next_school_day(account_id, today)
    # Am freien Tag gilt der Stand des letzten Schultags, wie am Freitagabend.
    try:
        from .study_plan import carry_day
        carry = carry_day(account_id, today)
    except Exception:
        carry = None
    ref = carry or today
    ref_iso = ref.isoformat()
    out: dict = {"next_school_day": nxt, "carry_day": carry.isoformat() if carry else None}

    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()  # wie /tasks?recent_done_days=14
    with closing(webapp_conn()) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT status,due_date FROM tasks WHERE account_id=? AND due_date IS NOT NULL AND due_date<=? "
            "AND (status!='done' OR COALESCE(completed_at, updated_at, '')>=?)",
            (account_id, nxt or today_iso, since))]
    ring = [t for t in rows if t["status"] != "done" or t["due_date"] >= ref_iso]
    open_ = sum(1 for t in ring if t["status"] != "done")
    out["tasks"] = {"done": len(ring) - open_, "total": len(ring)}

    try:
        from . import study_plan
        plan = study_plan.for_day(account_id, today, store=False)
        out["study"] = {"done": plan["done"], "total": plan["total"], "carry": plan.get("carry"),
                        "tight": plan["tight"][:1], "frozen": plan["frozen"]}
    except Exception:
        _LOG.warning("Lernplan für Konto %s nicht lesbar", account_id, exc_info=True)
        out["study"] = None

    day, _phase = bag_target(account_id, today, now)
    day = day or nxt
    out["bag"] = None
    if day:
        try:
            from .packing import packing_plan, view
            items, fingerprint, schedule_ = packing_plan(account_id, date.fromisoformat(day))
            with closing(webapp_conn()) as conn:
                bag = view(account_id, date.fromisoformat(day), items, fingerprint, conn, schedule_)
            out["bag"] = {"day": day, "done": bag["confirmed_count"], "total": len(bag["items"]),
                          "packed": bag["status"] == "packed"}
        except Exception:
            _LOG.warning("Packliste für Konto %s nicht lesbar", account_id, exc_info=True)

    hidden = hidden_keys(account_id)
    with closing(history_conn()) as hconn:
        lessons = [l for l in lessons_for_date(hconn, account_id, ref_iso) if not lesson_is_hidden(l, hidden)]
    # Ein vergangener Schultag ist ganz vorbei.
    clock = 24 * 60 if carry else now.hour * 60 + now.minute
    ended = [g for g in _merged([l for l in lessons if not l.get("is_cancelled") and not l.get("was_absent")
                                 and l.get("subject_name")])  # ohne Fach: keine Stunde (Klassenfahrt)
             if (_minutes(g[-1].get("end_time")) is not None and clock >= _minutes(g[-1].get("end_time")))]
    ids = [l["id"] for g in ended for l in g]
    rated: set = set()
    if ids:
        with closing(webapp_conn()) as conn:
            rated = {r[0] for r in conn.execute(
                f"SELECT lesson_id FROM lesson_checkins WHERE account_id=? AND rating IS NOT NULL "
                f"AND lesson_id IN ({','.join('?' * len(ids))})", (account_id, *ids))}
    open_fb = sum(1 for g in ended if _group_open(g, rated))
    # Vergessene Rückmeldungen der Tage davor bleiben offen, bis sie nachgeholt
    # sind (D210), wie überfällige Aufgaben.
    try:
        from .rewards import feedback_backlog
        older = [l for l in feedback_backlog(account_id, ref - timedelta(days=1), now)]
    except Exception:
        _LOG.warning("Offene Rückmeldungen für Konto %s nicht lesbar", account_id, exc_info=True)
        older = []
    by_day: dict[str, list[dict]] = {}
    for l in older:
        by_day.setdefault(l["date"], []).append(l)
    backlog = sum(len(_merged(day)) for day in by_day.values())
    ended_total, open_fb = len(ended) + backlog, open_fb + backlog
    out["feedback"] = {"done": ended_total - open_fb, "total": ended_total, "backlog": backlog}
    return out


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
                     "detail": " · ".join(_where(r) for r in retakes[:2]) + f" · {_brief(retakes[0]['reason'])}",
                     "go": go("erledigen", parent=True)})
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


# --- Stundenplan: heute und der nächste Schultag (D170) ----------------------
# Immer der heutige und der nächste Schultag, gewechselt wird um Mitternacht:
# Morgens sieht man, was heute ansteht, nachmittags im Rückblick, ob das Kind
# früher Schluss hatte, und schon den nächsten Tag. Ohne Schule heute die
# nächsten zwei Schultage. Ein Tag, an dem alles ausfällt, bleibt sichtbar.
SCHEDULE_DAYS = 2
SCHEDULE_LOOKAHEAD = 21


def _subject(lesson: dict) -> str:
    return subject_label(lesson.get("subject_name") or lesson.get("subject_short") or "")


def _state(lesson: dict) -> str:
    if lesson.get("is_cancelled"):
        return "cancelled"
    if lesson.get("is_subject_substituted") or lesson.get("is_teacher_substituted") or lesson.get("is_irregular"):
        return "sub"
    return "normal"


def day_changes(periods: list[dict]) -> list[dict]:
    """Was an einem Tag vom Plan abweicht, in Worten und ungekürzt: Ausfälle
    (eine Doppelstunde als eine Zeile), Vertretungen, Raumwechsel. Die Leiste
    der Familienkarte (D170) und die Woche (D184) lesen dieselbe Liste."""
    out, groups = [], {}
    for p in periods:
        if p["state"] == "cancelled":
            groups.setdefault(p["subject"], []).append(p)
    for subject, items in groups.items():
        out.append({"kind": "cancelled", "subject": subject, "start": items[0]["start"],
                    "text": f"{subject} {items[0]['start']}–{items[-1]['end']} fällt aus" if len(items) > 1
                    else f"{subject} {items[0]['start']} fällt aus"})
    out += [{"kind": "sub", "subject": p["subject"], "start": p["start"], "text": f"{p['subject']} {p['start']} Vertretung"}
            for p in periods if p["state"] == "sub"]
    out += [{"kind": "room", "subject": p["subject"], "start": p["start"], "text": f"{p['subject']} in Raum {p['room']}"}
            for p in periods if p["room_changed"] and p["state"] != "cancelled" and p["room"]]
    return out


def schedule_day(day: str, lessons: list[dict], today: date, now: datetime, exam_subjects: set[str]) -> dict:
    """Ein Schultag als Leiste: Stunden mit Zustand, Beginn und Ende nach Plan
    und tatsächlich, und in Worten, was abweicht."""
    lessons = sorted(lessons, key=lambda l: (l.get("start_time") or 0, l.get("end_time") or 0))
    held = [l for l in lessons if not l.get("is_cancelled")]
    is_today = day == today.isoformat()
    clock = now.hour * 100 + now.minute
    periods = []
    for l in lessons:
        start, end = _clock(l.get("start_time")), _clock(l.get("end_time"))
        exam = bool(l.get("exam")) or (not l.get("is_cancelled") and _subject(l).casefold() in exam_subjects)
        periods.append({"short": (l.get("subject_short") or _subject(l)[:3] or "?")[:4], "subject": _subject(l),
                        "start": l.get("start_hhmm"), "end": l.get("end_hhmm"), "state": _state(l), "exam": exam,
                        "room_changed": bool(l.get("is_room_substituted")), "room": l.get("room"),
                        "absent": bool(l.get("was_absent")),
                        "now": bool(is_today and start is not None and end is not None and start <= clock < end),
                        "past": bool(is_today and end is not None and end <= clock)})
    planned_start = min((_clock(l.get("start_time")) for l in lessons if _clock(l.get("start_time")) is not None), default=None)
    planned_end = max((_clock(l.get("end_time")) for l in lessons if _clock(l.get("end_time")) is not None), default=None)
    start = min((_clock(l.get("start_time")) for l in held if _clock(l.get("start_time")) is not None), default=None)
    end = max((_clock(l.get("end_time")) for l in held if _clock(l.get("end_time")) is not None), default=None)
    fmt = lambda v: f"{v // 100:02d}:{v % 100:02d}" if v is not None else None
    changes = day_changes(periods)
    notes = [c["text"] for c in changes]
    notes += [f"{p['subject']}: Arbeit" for p in periods if p["exam"]][:1]
    all_out = bool(lessons) and not held
    early = bool(end and planned_end and end < planned_end)
    late = bool(start and planned_start and start > planned_start)
    headline = ("fällt ganz aus" if all_out else
                " · ".join(filter(None, [f"später Beginn {fmt(start)}" if late else "",
                                         f"früher Schluss {fmt(end)} statt {fmt(planned_end)}" if early else ""])))
    return {"date": day, "label": "Heute" if is_today else day_label(day), "is_today": is_today,
            "start": fmt(start), "end": fmt(end), "planned_start": fmt(planned_start), "planned_end": fmt(planned_end),
            "early_end": early, "late_start": late, "all_cancelled": all_out, "headline": headline,
            "deviates": bool(headline or notes), "notes": notes[:4], "changes": changes, "periods": periods}


def schedule(account_id: int, today: date, now: datetime, upcoming: list[dict] | None = None) -> list[dict]:
    """Der heutige und der nächste Schultag, ohne Schule heute die nächsten zwei."""
    hidden = hidden_keys(account_id)
    exams: dict[str, set[str]] = {}
    for e in upcoming or []:
        exams.setdefault(e.get("date") or "", set()).add(subject_label(e.get("subject_name") or "").casefold())
    days = []
    with closing(history_conn()) as conn:
        for offset in range(SCHEDULE_LOOKAHEAD):
            day = (today + timedelta(days=offset)).isoformat()
            lessons = [l for l in lessons_for_date(conn, account_id, day) if not lesson_is_hidden(l, hidden)]
            if lessons:
                days.append(schedule_day(day, lessons, today, now, exams.get(day, set())))
            if len(days) >= SCHEDULE_DAYS:
                break
    return days


def board(account_id: int, tasks: list[dict], upcoming: list[dict], entries: list[dict],
          support: list[dict], today: date, now: datetime, evening_from: str) -> dict:
    evening = now.strftime("%H:%M") >= evening_from
    rows, ok = acute(account_id, tasks, today, now, evening)
    near, later = exam_rows(account_id, upcoming, entries, today)
    try:
        days = schedule(account_id, today, now, upcoming)
    except Exception:
        _LOG.warning("Stundenplan für Konto %s nicht lesbar", account_id, exc_info=True)
        days = []
    return {"status": level(rows, near), "acute": rows, "ok": ok, "evening": evening, "schedule": days,
            "exams": near, "later": later, "watch": watch(account_id, support, today)}
