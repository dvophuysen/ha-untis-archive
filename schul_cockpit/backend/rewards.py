"""Serie, Abzeichen und Jahresmedaille für die Routine (D172, D173).

Gezählt wird nur, was das Kind selbst tut: eigene Anmeldung oder „Kind am
Elterngerät“ (D175). Mitlesen und Testmodus zählen nie. Alles gilt ab dem Tag,
an dem das System eingeführt wurde; frühere Tage zählen nicht.

„Geschafft“ ist ein Schultag, an dem zu einem Zeitpunkt alles erledigt war:
keine offene Aufgabe bis zum nächsten Schultag, die Pflichtschritte des
Lernplans erledigt (D180), die Tasche für den nächsten Schultag gepackt, die
Stunden des Tages zurückgemeldet, und das Kind hat an dem Tag selbst etwas
bestätigt. Ein offener Tag lässt sich bis zum Beginn der
ersten Stunde des nächsten Schultags retten, höchstens einmal je Kalenderwoche;
er hält die Serie, zählt aber halb.
"""

from __future__ import annotations

import logging
from contextlib import closing
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .db import history_conn, webapp_conn
from .request_cache import memo

LOG = logging.getLogger("schul_cockpit.rewards")
TZ = ZoneInfo("Europe/Berlin")
DEFAULT_BONUS = "17:00"

STREAK_MILESTONES = (5, 10, 20, 40, 60, 100, 150, 190)
LEVELS = ("Bronze", "Silber", "Gold", "Platin", "Diamant")
BADGES = (
    # Schlüssel, Name, Emoji, wofür, Grenzen je Stufe
    ("geschafft", "Geschafft", "✅", "geschaffte Schultage insgesamt", (10, 50, 190, 500, 1000)),
    ("dranbleiber", "Dranbleiber", "🔥", "längste Serie", (5, 20, 60, 120, 190)),
    ("packprofi", "Packprofi", "🎒", "Tasche komplett gepackt", (10, 50, 190, 500, 1000)),
    ("notiert", "Notiert", "📝", "Aufgaben und Erinnerungen selbst eingetragen", (5, 25, 100, 300, 750)),
    ("fruehstarter", "Frühstarter", "⚡", "vor der Bonuszeit geschafft", (5, 30, 120, 350, 800)),
    ("ehrlich", "Ehrlich", "💬", "Stunden zurückgemeldet", (50, 300, 1000, 3000, 6000)),
    ("wortschatz", "Wortschatz", "🗣️", "Vokabeln geübt", (100, 1000, 5000, 15000, 40000)),
    ("vorbereitet", "Vorbereitet", "🎯", "vor einer Arbeit alle Themen angefangen", (1, 5, 15, 40, 80)),
    # Stufe C (D181): gemessen an Übungsarbeiten und Raster, gezählt in reward_extras.
    ("probearbeit", "Probearbeit", "📄", "Probearbeiten geschrieben und ausgewertet", (1, 5, 15, 40, 80)),
    ("aufsteiger", "Aufsteiger", "📈", "Themen und Bereiche, die erstmals sicher wurden", (5, 25, 100, 250, 500)),
    ("zielniveau", "Zielniveau", "🏁", "vor einer Arbeit alle Themen auf Zielniveau", (1, 3, 10, 25, 50)),
    ("extrameile", "Extrameile", "➕", "freiwillig mehr geübt als das Pensum", (5, 20, 60, 150, 300)),
)
# Im Einführungsschuljahr sind die Jahresmedaillen leichter (D173).
MEDAL_LIMITS = {"2026/27": (0.50, 0.65, 0.80)}
MEDAL_DEFAULT = (0.60, 0.75, 0.90)
MEDALS = ("Bronze", "Silber", "Gold")


def now_local() -> datetime:
    return datetime.now(TZ)


# ----------------------------------------------------------------- Grundlagen

def start_day() -> date:
    """Der Einführungstag. Beim ersten Aufruf festgehalten, danach fest."""
    with closing(webapp_conn()) as c, c:
        row = c.execute("SELECT start_day FROM reward_config WHERE id=1").fetchone()
        if row:
            return date.fromisoformat(row["start_day"])
        today = now_local().date()
        c.execute("INSERT OR IGNORE INTO reward_config(id,start_day) VALUES(1,?)", (today.isoformat(),))
        return date.fromisoformat(c.execute("SELECT start_day FROM reward_config WHERE id=1").fetchone()["start_day"])


def bonus_until(account_id: int) -> str:
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT bonus_until FROM reward_settings WHERE account_id=?", (account_id,)).fetchone()
    return row["bonus_until"] if row and row["bonus_until"] else DEFAULT_BONUS


def set_bonus_until(account_id: int, value: str) -> str:
    h, m = (int(x) for x in value.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Uhrzeit ungültig")
    value = f"{h:02d}:{m:02d}"
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO reward_settings(account_id,bonus_until) VALUES(?,?) "
                  "ON CONFLICT(account_id) DO UPDATE SET bonus_until=excluded.bonus_until", (account_id, value))
    return value


def acting_child(user) -> bool:
    from . import view_mode
    if view_mode.current.get() == "test":
        return False
    return getattr(user, "role", None) == "child" or view_mode.current.get() == "child"


@memo(shallow=True)  # die Stunden liest jeder Aufrufer nur
def _lessons(account_id: int, first: date, last: date) -> list[dict]:
    from .courses import hidden_keys, lesson_is_hidden
    from .queries import lessons_in_range
    try:
        with closing(history_conn()) as c:
            rows = lessons_in_range(c, account_id, first.isoformat(), last.isoformat())
        hidden = hidden_keys(account_id)
    except Exception:
        LOG.debug("Stundenplan für Konto %s nicht lesbar", account_id, exc_info=True)
        return []
    return [l for l in rows if not lesson_is_hidden(l, hidden)]


def _held(l: dict) -> bool:
    return not l.get("is_cancelled") and not l.get("was_absent")


def school_days(account_id: int, first: date, last: date) -> list[date]:
    """Tage mit wenigstens einer Stunde, die stattfand. Ferien, Wochenenden und
    Tage, an denen das Kind ganz fehlte, halten die Serie an."""
    return sorted({date.fromisoformat(l["date"]) for l in _lessons(account_id, first, last) if _held(l)})


def _minutes(hhmm) -> int | None:
    return hhmm // 100 * 60 + hhmm % 100 if isinstance(hhmm, int) else None


def _first_start(account_id: int, day: date) -> datetime | None:
    starts = [_minutes(l["start_time"]) for l in _lessons(account_id, day, day) if _held(l)]
    starts = [s for s in starts if s is not None]
    return datetime.combine(day, time(min(starts) // 60, min(starts) % 60), TZ) if starts else None


# ------------------------------------------------------------------- Erfassen

def note(account_id: int, kind: str, ref: str | int, user, when: datetime | None = None) -> None:
    """Eine Handlung des Kindes festhalten und den Tag neu prüfen.

    kind: task, note, feedback, bag, vocab. Jede Handlung zählt einmal (ref)."""
    if not acting_child(user):
        return
    when = when or now_local()
    try:
        with closing(webapp_conn()) as c, c:
            c.execute("INSERT OR IGNORE INTO reward_events(account_id,kind,ref,day,created_at) VALUES(?,?,?,?,?)",
                      (account_id, kind, str(ref), when.date().isoformat(), when.isoformat()))
            c.execute("INSERT OR IGNORE INTO reward_activity(account_id,day,first_at) VALUES(?,?,?)",
                      (account_id, when.date().isoformat(), when.isoformat()))
        _freeze_plan(account_id, when.date())
        evaluate(account_id, when)
    except Exception:
        # Belohnung ist Beiwerk: Sie darf nie eine Handlung des Kindes scheitern lassen.
        LOG.warning("Belohnung für Konto %s nicht erfasst", account_id, exc_info=True)


def _freeze_plan(account_id: int, day: date) -> None:
    """Der Lernplan des Tages steht fest, bevor der Tag als geschafft zählen
    kann (D180); sonst hätte ein Tag ohne geöffnetes „Heute“ keine Lernpflicht."""
    try:
        from . import study_plan
        study_plan.ensure(account_id, day)
    except Exception:
        LOG.warning("Lernplan für Konto %s nicht berechenbar", account_id, exc_info=True)


def _learning_open(account_id: int, day: date, now: datetime) -> int:
    try:
        from . import study_plan
        return study_plan.open_count(account_id, day, max(day, now.date()))
    except Exception:
        LOG.warning("Lernplan für Konto %s nicht prüfbar", account_id, exc_info=True)
        return 0


def note_prepared(account_id: int, exams: list[dict], today: date | None = None) -> None:
    """„Vorbereitet“: Am Tag vor einer Arbeit oder am Tag selbst sind alle Themen
    mindestens angefangen. Zählt Einsatz, nicht Ergebnis."""
    from . import lernstand
    today = today or now_local().date()
    if today < start_day():
        return
    for e in exams or []:
        try:
            days = (date.fromisoformat(e["date"]) - today).days
        except (KeyError, ValueError, TypeError):
            continue
        if not 0 <= days <= 1 or not e.get("exam_key"):
            continue
        try:
            topics = [t for t in lernstand.topics_for(account_id, e["exam_key"], e.get("subject_name"), with_material=False)
                      if not t.get("stale")]
            counts = lernstand.stage_counts(topics)
        except Exception:
            continue
        if topics and not counts.get("neu"):
            with closing(webapp_conn()) as c, c:
                c.execute("INSERT OR IGNORE INTO reward_events(account_id,kind,ref,day,created_at) VALUES(?,?,?,?,?)",
                          (account_id, "prepared", e["exam_key"], today.isoformat(), now_local().isoformat()))


# ------------------------------------------------------------------- Bewerten

def _next_school_day(account_id: int, after: date) -> date | None:
    days = school_days(account_id, after + timedelta(days=1), after + timedelta(days=21))
    return days[0] if days else None


def _open_tasks(c, account_id: int, until: date) -> int:
    return c.execute("SELECT COUNT(*) FROM tasks WHERE account_id=? AND status NOT IN ('done','skipped') "
                     "AND due_date IS NOT NULL AND due_date<=?", (account_id, until.isoformat())).fetchone()[0]


def _bag_packed(c, account_id: int, day: date) -> bool:
    from .packing import packing_plan
    items, _, _ = packing_plan(account_id, day)
    if not items:
        return True
    done = {r["item_key"] for r in c.execute(
        "SELECT item_key FROM packing_items WHERE account_id=? AND school_day=? AND done=1", (account_id, day.isoformat()))}
    return all(i["key"] in done for i in items)


def _feedback_open(c, account_id: int, day: date, now: datetime) -> int:
    lessons = [l for l in _lessons(account_id, day, day) if _held(l)]
    ended = [l for l in lessons if day < now.date() or (_minutes(l.get("end_time")) or 0) <= now.hour * 60 + now.minute]
    if not ended:
        return 0
    rated = {r["lesson_id"] for r in c.execute(
        f"SELECT lesson_id FROM lesson_checkins WHERE account_id=? AND rating IS NOT NULL AND lesson_id IN ({','.join('?' * len(ended))})",
        (account_id, *[l["id"] for l in ended]))}
    return sum(1 for l in ended if l["id"] not in rated)


def day_state(account_id: int, day: date, now: datetime) -> dict:
    """Was an einem Schultag noch fehlt, gemessen am jetzigen Stand."""
    nxt = _next_school_day(account_id, day)
    with closing(webapp_conn()) as c:
        tasks = _open_tasks(c, account_id, nxt or day)
        bag = _bag_packed(c, account_id, nxt) if nxt else True
        feedback = _feedback_open(c, account_id, day, now)
    learning = _learning_open(account_id, day, now)
    return {"next": nxt, "open_tasks": tasks, "bag_packed": bag, "feedback_open": feedback,
            "learning_open": learning, "clear": not tasks and bag and not feedback and not learning}


def _has_activity(c, account_id: int, *days: date) -> bool:
    return bool(c.execute(f"SELECT 1 FROM reward_activity WHERE account_id=? AND day IN ({','.join('?' * len(days))})",
                          (account_id, *[d.isoformat() for d in days])).fetchone())


def evaluate(account_id: int, now: datetime | None = None) -> None:
    """Den heutigen Tag als geschafft oder einen offenen Vortag als gerettet eintragen."""
    now = now or now_local()
    today = now.date()
    start = start_day()
    if today < start:
        return
    recent = school_days(account_id, today - timedelta(days=14), today)
    with closing(webapp_conn()) as c, c:
        done = {r["school_day"] for r in c.execute(
            "SELECT school_day FROM reward_days WHERE account_id=? AND school_day>=?",
            (account_id, (today - timedelta(days=14)).isoformat()))}
        # Heute geschafft?
        if today in recent and today.isoformat() not in done and _has_activity(c, account_id, today):
            if day_state(account_id, today, now)["clear"]:
                h, m = (int(x) for x in bonus_until(account_id).split(":"))
                c.execute("INSERT OR IGNORE INTO reward_days(account_id,school_day,kind,done_at,bonus) VALUES(?,?,?,?,?)",
                          (account_id, today.isoformat(), "full", now.isoformat(), int(now.time() < time(h, m))))
                return
        # Den letzten Schultag vor heute retten?
        past = [d for d in recent if d < today and d >= start]
        if not past:
            return
        prev = past[-1]
        if prev.isoformat() in done:
            return
        nxt = _next_school_day(account_id, prev)
        # Wochenende und Ferien (D178): Der letzte Schultag davor zählt voll, wenn
        # bis zum Abend vor dem nächsten Schultag alles erledigt ist. Erst danach,
        # am Morgen vor der ersten Stunde, ist es ein Retten.
        if nxt and (nxt - prev).days > 1 and prev < today < nxt:
            free = [prev + timedelta(days=i) for i in range((today - prev).days + 1)]
            if _has_activity(c, account_id, *free) and day_state(account_id, prev, now)["clear"]:
                c.execute("INSERT OR IGNORE INTO reward_days(account_id,school_day,kind,done_at,bonus) VALUES(?,?,?,?,0)",
                          (account_id, prev.isoformat(), "full", now.isoformat()))
            return
        first = _first_start(account_id, nxt) if nxt else None
        if not first or now >= first:
            return
        week = prev - timedelta(days=prev.weekday())
        used = c.execute("SELECT COUNT(*) FROM reward_days WHERE account_id=? AND kind='rescued' AND school_day BETWEEN ? AND ?",
                         (account_id, week.isoformat(), (week + timedelta(days=6)).isoformat())).fetchone()[0]
        if used or not _has_activity(c, account_id, prev, today):
            return
        if day_state(account_id, prev, now)["clear"]:
            c.execute("INSERT OR IGNORE INTO reward_days(account_id,school_day,kind,done_at,bonus) VALUES(?,?,?,?,0)",
                      (account_id, prev.isoformat(), "rescued", now.isoformat()))


# ----------------------------------------------------------------- Auswertung

def school_year(day: date) -> str:
    first = day.year if day.month >= 8 else day.year - 1
    return f"{first}/{str(first + 1)[2:]}"


def _level(value: int, limits: tuple) -> int:
    return sum(1 for x in limits if value >= x)


def summary(account_id: int, now: datetime | None = None) -> dict:
    now = now or now_local()
    today = now.date()
    start = start_day()
    evaluate(account_id, now)
    days = school_days(account_id, start, today)
    with closing(webapp_conn()) as c, c:
        rows = {r["school_day"]: dict(r) for r in c.execute(
            "SELECT * FROM reward_days WHERE account_id=? AND school_day>=?", (account_id, start.isoformat()))}
        events = {r["kind"]: r["n"] for r in c.execute(
            "SELECT kind, COUNT(*) n FROM reward_events WHERE account_id=? AND day>=? GROUP BY kind",
            (account_id, start.isoformat()))}
        stored = {(r["badge"], r["level"]) for r in c.execute(
            "SELECT badge, level FROM reward_badges WHERE account_id=?", (account_id,))}

        state = {d: (rows.get(d.isoformat()) or {}).get("kind") for d in days}
        # Serie: vom heutigen Tag rückwärts; ein noch offener heutiger Tag bricht nichts.
        streak = 0
        for d in reversed(days):
            if state[d]:
                streak += 1
            elif d == today:
                continue
            elif _rescuable(account_id, d, days, now):
                continue
            else:
                break
        record, run, runs_ended = 0, 0, []
        for d in days:
            if state[d]:
                run += 1
                record = max(record, run)
            elif d != today and not _rescuable(account_id, d, days, now):
                if run:
                    runs_ended.append(run)
                run = 0
        total = sum(1 for d in days if state[d])
        full_weeks = _full_weeks(days, state, today)

        counts = {
            "geschafft": total, "dranbleiber": record, "packprofi": events.get("bag", 0),
            "notiert": events.get("note", 0), "ehrlich": events.get("feedback", 0),
            "wortschatz": events.get("vocab", 0), "vorbereitet": events.get("prepared", 0),
            "fruehstarter": sum(1 for r in rows.values() if r["kind"] == "full" and r["bonus"]),
        }
        from .reward_extras import counts as extra_counts
        counts.update(extra_counts(account_id, start, today))
        badges, new = [], []
        for key, name, emoji, what, limits in BADGES:
            value = counts[key]
            level = _level(value, limits)
            # Fällt die Grundlage weg (eine Auswertung zurückgehalten oder
            # korrigiert), wird eine gespeicherte Stufe zurückgenommen (D203).
            gone = [lv for (k, lv) in stored if k == key and lv > level]
            if gone:
                c.execute(f"DELETE FROM reward_badges WHERE account_id=? AND badge=? AND level IN ({','.join('?' * len(gone))})",
                          (account_id, key, *gone))
                LOG.info("Abzeichen %s Stufe %s für Konto %s zurückgenommen", key, gone, account_id)
            for lv in range(1, level + 1):
                if (key, lv) not in stored:
                    c.execute("INSERT OR IGNORE INTO reward_badges(account_id,badge,level,reached_at) VALUES(?,?,?,?)",
                              (account_id, key, lv, now.isoformat()))
                    new.append({"key": key, "name": name, "emoji": emoji, "level": LEVELS[lv - 1]})
            badges.append({"key": key, "name": name, "emoji": emoji, "what": what, "value": value,
                           "level": level, "level_name": LEVELS[level - 1] if level else None,
                           "next": limits[level] if level < len(limits) else None,
                           "prev": limits[level - 1] if level else 0, "limits": list(limits)})
        reached_today = [dict(r) for r in c.execute(
            "SELECT badge, level, reached_at FROM reward_badges WHERE account_id=? AND reached_at>=?",
            (account_id, datetime.combine(today, time(0), TZ).isoformat()))]

    special = [
        {"key": "volle_woche", "name": "Volle Woche", "emoji": "🗓️", "count": len(full_weeks)},
        {"key": "comeback", "name": "Comeback", "emoji": "↩️", "count": int(any(r >= 10 for r in runs_ended[1:] + ([run] if runs_ended else [])))},
        {"key": "letzte_schulwoche", "name": "Letzte Schulwoche", "emoji": "🏖️", "count": _last_weeks(account_id, full_weeks, days)},
    ]
    week_start = today - timedelta(days=today.weekday())
    week_days = school_days(account_id, week_start, week_start + timedelta(days=4))
    week = []
    for i in range(5):
        d = week_start + timedelta(days=i)
        if d < start:
            s = "before"
        elif d not in week_days:
            s = "free"
        elif rows.get(d.isoformat()):
            s = rows[d.isoformat()]["kind"]
        elif d >= today or _rescuable(account_id, d, days, now):
            s = "open"
        else:
            s = "missed"
        week.append({"day": d.isoformat(), "state": s})
    today_row = rows.get(today.isoformat())
    return {
        "start": start.isoformat(),
        "today": {"school_day": today in days, "done": bool(today_row), "kind": (today_row or {}).get("kind"),
                  "bonus": bool((today_row or {}).get("bonus"))},
        "streak": {"current": streak, "record": record,
                   "next_milestone": next((m for m in STREAK_MILESTONES if m > streak), None)},
        "total": total,
        "bonus_until": bonus_until(account_id),
        "week": week,
        "badges": badges,
        "special": special,
        "medals": _medals(days, state, today, start),
        "new_badges": new,
        "reached_today": reached_today,
    }


def _rescuable(account_id: int, day: date, days: list[date], now: datetime) -> bool:
    """Ein offener Tag, dessen Rettungsfrist noch läuft, gilt noch nicht als verpasst."""
    later = [d for d in days if d > day]
    if later and later[0] < now.date():
        return False
    nxt = _next_school_day(account_id, day)
    first = _first_start(account_id, nxt) if nxt else None
    return bool(first and now < first and day < now.date())


def _full_weeks(days: list[date], state: dict, today: date) -> list[date]:
    weeks: dict[date, list[date]] = {}
    for d in days:
        weeks.setdefault(d - timedelta(days=d.weekday()), []).append(d)
    this_week = today - timedelta(days=today.weekday())
    return [w for w, ds in weeks.items() if w < this_week and all(state[d] for d in ds)
            or (w == this_week and today.weekday() >= 4 and all(state[d] for d in ds) and max(ds) <= today)]


def _last_weeks(account_id: int, full_weeks: list[date], days: list[date]) -> int:
    """Volle Wochen, nach denen mindestens eine Woche keine Schule kommt."""
    count = 0
    for w in full_weeks:
        after = school_days(account_id, w + timedelta(days=7), w + timedelta(days=13))
        if not after:
            count += 1
    return count


def _medals(days: list[date], state: dict, today: date, start: date) -> list[dict]:
    years: dict[str, list[date]] = {}
    for d in days:
        years.setdefault(school_year(d), []).append(d)
    current = school_year(today)
    years.setdefault(current, [])
    out = []
    for label in sorted(years):
        ds = [d for d in years[label] if d < today or state.get(d)]
        score = sum(1 if state.get(d) == "full" else 0.5 if state.get(d) == "rescued" else 0 for d in ds)
        pct = score / len(ds) if ds else 0.0
        limits = MEDAL_LIMITS.get(label, MEDAL_DEFAULT)
        level = sum(1 for x in limits if pct >= x)
        out.append({"year": label, "pct": round(pct * 100), "days": len(ds), "level": level,
                    "medal": MEDALS[level - 1] if level else None, "running": label == current,
                    "limits": [round(x * 100) for x in limits]})
    return out
