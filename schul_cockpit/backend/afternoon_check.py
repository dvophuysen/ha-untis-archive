"""Der Moment nach dem Unterricht: Steht alles von heute in der App?

Das wiederkehrende Problem ist nicht nur das Vergessen der Erledigung, sondern
dass eine Aufgabe gar nicht erst notiert wird (VERANTWORTUNG.md, Stufe 2).
Kurz nach der letzten Stunde fragt die App einmal nach. Die Antwort ist ein
Foto oder „nichts Neues“, sonst nichts: Fach, Titel und Fälligkeit der
Aufgabe kommen aus der Lesung des Fotos und dem Stundenplan.
"""

from __future__ import annotations

import logging
from contextlib import closing
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import app_notify
from .courses import hidden_keys, lesson_is_hidden
from .db import history_conn, webapp_conn
from .packing import packing_plan
from .queries import lessons_in_range
from .subject_names import key as subject_key
from .subject_names import label as subject_label

LOG = logging.getLogger("schul_cockpit.afternoon")
ZONE = ZoneInfo("Europe/Berlin")
DEFAULT_DELAY = 20          # Minuten nach der letzten Stunde
WINDOW = 1800               # wie reminders.due: keine Nachlieferung Stunden später
DEFAULT_EVENING = "18:00"
PROVISIONAL_TITLE = "Hausaufgabe (Foto wird gelesen)"
TITLE = "Alles von heute notiert?"
MESSAGE = "Steht jede Hausaufgabe von heute in der App? Kurz antippen: Foto oder „nichts Neues“."


def now_local() -> datetime:
    return datetime.now(ZONE)


def last_lesson_end(account_id: int, day: date) -> datetime | None:
    """Ende der letzten nicht ausgefallenen Stunde des Tages, ohne ausgeblendete Kurse."""
    try:
        _, _, schedule = packing_plan(account_id, day)
    except Exception:
        LOG.debug("Stundenplan für Konto %s am %s nicht lesbar", account_id, day)
        return None
    ends = [l["end_hhmm"] for l in schedule if l.get("end_hhmm") and not l.get("is_cancelled")]
    if not ends:
        return None
    hour, minute = map(int, max(ends).split(":"))
    return datetime.combine(day, time(hour, minute), tzinfo=ZONE)


def evening_from(account_id: int) -> str:
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT remind_at FROM reminder_settings WHERE account_id=?", (account_id,)).fetchone()
    return (row["remind_at"] if row and row["remind_at"] else DEFAULT_EVENING)


def answers(account_id: int, day: str) -> list[dict]:
    with closing(webapp_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT id,answer,material_id,task_id,created_at FROM afternoon_checks "
            "WHERE account_id=? AND school_day=? ORDER BY id", (account_id, day))]


def state(account_id: int, now: datetime | None = None) -> dict:
    now = (now or now_local()).astimezone(ZONE)
    day = now.date()
    end = last_lesson_end(account_id, day)
    given = answers(account_id, day.isoformat())
    hour, minute = map(int, evening_from(account_id).split(":"))
    evening = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    closed = any(a["answer"] == "nothing" for a in given)
    active = end is not None and end <= now < evening and not closed
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT afternoon_enabled,afternoon_delay FROM reminder_settings WHERE account_id=?",
                        (account_id,)).fetchone()
    return {
        "date": day.isoformat(),
        "school_day": end is not None,
        "last_lesson_end": end.strftime("%H:%M") if end else None,
        "active": active,
        "closed": closed,
        "answers": given,
        "photos": sum(1 for a in given if a["answer"] == "photo"),
        "enabled": bool(row and row["afternoon_enabled"]),
        "delay": (row["afternoon_delay"] if row else None) or DEFAULT_DELAY,
    }


def record(account_id: int, day: str, answer: str, user_id: int | None,
           material_id: int | None = None, task_id: int | None = None) -> int:
    with closing(webapp_conn()) as c, c:
        return c.execute(
            "INSERT INTO afternoon_checks(account_id,school_day,answer,material_id,task_id,user_id,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (account_id, day, answer, material_id, task_id, user_id, now_local().isoformat())).lastrowid


def notify(setting: dict, now: datetime) -> int:
    """Die Mitteilung nach der Schule: einmal je Gerät und Tag, nur wenn
    eingeschaltet, nur an Schultagen, nur solange niemand geantwortet hat."""
    account = setting["account_id"]
    if not setting.get("afternoon_enabled"):
        return 0
    day = now.date()
    end = last_lesson_end(account, day)
    if end is None:
        return 0
    target = end + timedelta(minutes=setting.get("afternoon_delay") or DEFAULT_DELAY)
    if not 0 <= (now - target).total_seconds() < WINDOW:
        return 0
    if answers(account, day.isoformat()):
        return 0
    sent, url = 0, app_notify.own_panel()
    for service in app_notify.targets(account):
        with closing(webapp_conn()) as c, c:
            c.execute("BEGIN IMMEDIATE")
            claimed = c.execute(
                "INSERT OR IGNORE INTO afternoon_app_deliveries(account_id,school_day,service,status,created_at) "
                "VALUES(?,?,?,'claimed',?)", (account, day.isoformat(), service, now.isoformat())).rowcount
        if not claimed:
            continue
        ok = app_notify.send(service, TITLE, MESSAGE, url)
        with closing(webapp_conn()) as c, c:
            c.execute("UPDATE afternoon_app_deliveries SET status=? WHERE account_id=? AND school_day=? AND service=?",
                      ("accepted" if ok else "failed", account, day.isoformat(), service))
        sent += int(ok)
    return sent


def _lessons_after(account_id: int, after: date, days: int) -> list[dict]:
    try:
        with closing(history_conn()) as c:
            rows = lessons_in_range(c, account_id, (after + timedelta(days=1)).isoformat(),
                                    (after + timedelta(days=days)).isoformat())
    except Exception:
        LOG.debug("Stundenplan nach %s für Konto %s nicht lesbar", after, account_id)
        return []
    hidden = hidden_keys(account_id)
    rows = [l for l in rows if not l.get("is_cancelled") and not lesson_is_hidden(l, hidden)]
    return sorted(rows, key=lambda l: (l.get("date") or "", l.get("start_time") or 0))


def next_lesson_date(account_id: int, subject: str | None, after: date, days: int = 21) -> str | None:
    """Der Tag der nächsten Stunde dieses Fachs: die Hausaufgabe ist bis dahin fällig."""
    if not subject:
        return None
    wanted = subject_key(subject)
    for lesson in _lessons_after(account_id, after, days):
        if subject_key(lesson.get("subject_name")) == wanted:
            return lesson["date"]
    return None


def next_school_day(account_id: int, after: date, days: int = 14) -> str | None:
    for lesson in _lessons_after(account_id, after, days):
        return lesson["date"]
    return None


def intake_photo(account_id: int, user_id: int | None, content: bytes, filename: str, mime: str,
                 now: datetime | None = None) -> dict:
    """Das Foto wird abgelegt und die Aufgabe sofort angelegt, vorläufig fällig
    zum nächsten Schultag. Die Lesung trägt danach Fach, Titel und den Termin
    der nächsten Stunde nach (`refine`). Das Kind wartet auf nichts."""
    from . import materials as store
    now = (now or now_local()).astimezone(ZONE)
    day = now.date()
    material_id = store.create(account_id, user_id, content, filename, mime,
                               {"title": f"Foto nach der Schule, {day.strftime('%d.%m.')}"})
    due = next_school_day(account_id, day)
    stamp = now.isoformat()
    with closing(webapp_conn()) as c, c:
        task_id = c.execute(
            "INSERT INTO tasks(account_id,ha_uid,title,task_type,status,due_date,notes,source,"
            "created_by_user_id,created_at,updated_at) VALUES(?,NULL,?,'homework','open',?,?,'manual',?,?,?)",
            (account_id, PROVISIONAL_TITLE, due,
             "Nach der Schule fotografiert. Fach, Titel und Termin kommen aus der Lesung des Fotos.",
             user_id, stamp, stamp)).lastrowid
        c.execute("INSERT OR IGNORE INTO material_links(material_id,kind,target_id,origin,created_at) "
                  "VALUES(?,'task',?,'mensch',?)", (material_id, task_id, stamp))
    record(account_id, day.isoformat(), "photo", user_id, material_id, task_id)
    return {"material_id": material_id, "task_id": task_id, "due_date": due}


def refine(account_id: int, material_id: int) -> dict | None:
    """Nach der Lesung: Fach und Titel aus dem Material, Fälligkeit aus der
    nächsten Stunde des Fachs. Einmal, und nur solange die Aufgabe offen ist."""
    with closing(webapp_conn()) as c:
        check = c.execute("SELECT id,task_id,school_day,refined_at FROM afternoon_checks "
                          "WHERE account_id=? AND material_id=? AND task_id IS NOT NULL",
                          (account_id, material_id)).fetchone()
        if not check or check["refined_at"]:
            return None
        material = c.execute("SELECT subject_name,title,summary,analysis_state FROM materials WHERE id=? AND account_id=?",
                             (material_id, account_id)).fetchone()
        task = c.execute("SELECT id,title,status FROM tasks WHERE id=? AND account_id=?",
                         (check["task_id"], account_id)).fetchone()
    if not material or material["analysis_state"] != "ready" or not task or task["status"] != "open":
        return None
    subject = (material["subject_name"] or "").strip() or None
    heading = (material["title"] or "").strip()
    if subject and heading:
        title = f"{subject_label(subject)}: {heading}"
    elif subject:
        title = f"{subject_label(subject)}: Hausaufgabe"
    else:
        title = heading or "Hausaufgabe (Foto)"
    values = {"title": title[:200], "subject_name": subject, "updated_at": now_local().isoformat()}
    due = next_lesson_date(account_id, subject, date.fromisoformat(check["school_day"]))
    if due:
        values["due_date"] = due
    with closing(webapp_conn()) as c, c:
        c.execute("UPDATE tasks SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
                  (*values.values(), task["id"]))
        c.execute("UPDATE afternoon_checks SET refined_at=? WHERE id=?", (values["updated_at"], check["id"]))
    LOG.info("Aufgabe %s aus Foto %s: %s, fällig %s", task["id"], material_id, title, due or "offen")
    return {"task_id": task["id"], **values}
