"""Der Wochenbericht an die Eltern als Mitteilung aufs Handy.

Einmal in der Woche, zur eingestellten Zeit, geht je Kind eine kurze
Nachricht an die ausgewählten Elterngeräte: die Kopfzeile des
Nutzungsberichts und die Auffälligkeiten in einem Satz. Tippen öffnet die
App. Geräte, die als Erinnerungsziel eines Kindes eingetragen sind, sind
ausgeschlossen, damit der Bericht nie bei den Kindern landet (D159, D161).
"""

from __future__ import annotations

import logging
import re
from contextlib import closing
from datetime import datetime, timedelta

from . import app_notify, usage_report
from .db import history_conn, webapp_conn

LOG = logging.getLogger("schul_cockpit.parent_report")
DEFAULT_WEEKDAY = 6  # Sonntag
DEFAULT_AT = "18:00"
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
WEEKDAYS = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


def child_devices() -> set[str]:
    """Alle Geräte, die irgendeinem Kind Erinnerungen schicken."""
    with closing(webapp_conn()) as c:
        return {r[0] for r in c.execute("SELECT service FROM reminder_app_targets")}


def config() -> dict:
    with closing(webapp_conn()) as c:
        row = c.execute("SELECT weekday,at FROM parent_report_config WHERE id=1").fetchone()
        targets = [r[0] for r in c.execute("SELECT service FROM parent_report_targets ORDER BY service")]
    weekday, at = (row["weekday"], row["at"]) if row else (DEFAULT_WEEKDAY, DEFAULT_AT)
    return {"weekday": weekday, "weekday_label": WEEKDAYS[weekday], "at": at, "targets": targets}


def set_config(weekday: int, at: str, targets: list[str]) -> dict:
    if not 0 <= weekday <= 6 or not TIME.match(at or ""):
        raise ValueError("Wochentag 0–6 und Uhrzeit HH:MM angeben.")
    kids = child_devices()
    wanted = sorted({s for s in targets if s.startswith(app_notify.PREFIX) and "/" not in s})
    blocked = [s for s in wanted if s in kids]
    if blocked:
        raise ValueError("Diese Geräte bekommen Erinnerungen eines Kindes: " + ", ".join(blocked))
    with closing(webapp_conn()) as c, c:
        c.execute("INSERT INTO parent_report_config(id,weekday,at) VALUES(1,?,?) "
                  "ON CONFLICT(id) DO UPDATE SET weekday=excluded.weekday,at=excluded.at", (weekday, at))
        c.execute("DELETE FROM parent_report_targets")
        c.executemany("INSERT INTO parent_report_targets(service) VALUES(?)", [(s,) for s in wanted])
    return config()


def accounts() -> list[tuple[int, str]]:
    conn = history_conn()
    try:
        return [(r["id"], r["name"]) for r in conn.execute("SELECT id,name FROM accounts ORDER BY id")]
    finally:
        conn.close()


def message_for(account_id: int, name: str, day) -> tuple[str, str]:
    report = usage_report.week(account_id, day)
    title = f"Woche {report['week']['label']}: {name}"
    text = report["headline"]
    if report["warnings"]:
        text += ". Auffällig: " + "; ".join(w["title"] for w in report["warnings"][:3])
        if len(report["warnings"]) > 3:
            text += " …"
    return title, text + "."


def send_all(now: datetime, *, week_key: str | None = None) -> dict:
    """Je Kind und Gerät eine Nachricht. Mit week_key nur einmal je Woche."""
    targets = [s for s in config()["targets"] if s not in child_devices()]
    if not targets:
        return {}
    url = app_notify.own_panel()
    sent: dict[str, int] = {}
    for account_id, name in accounts():
        try:
            title, text = message_for(account_id, name, now.date())
        except Exception:
            LOG.warning("Wochenbericht für Konto %s nicht erstellbar", account_id, exc_info=True)
            continue
        for service in targets:
            if week_key:
                with closing(webapp_conn()) as c, c:
                    c.execute("BEGIN IMMEDIATE")
                    claimed = c.execute(
                        "INSERT OR IGNORE INTO parent_report_deliveries(week,account_id,service,status,created_at) "
                        "VALUES(?,?,?,'claimed',?)", (week_key, account_id, service, now.isoformat())).rowcount
                if not claimed:
                    continue
            ok = app_notify.send(service, title, text, url)
            if week_key:
                with closing(webapp_conn()) as c, c:
                    c.execute("UPDATE parent_report_deliveries SET status=? WHERE week=? AND account_id=? AND service=?",
                              ("accepted" if ok else "failed", week_key, account_id, service))
            sent[service] = sent.get(service, 0) + int(ok)
    return sent


def run_once(now: datetime) -> None:
    """Aus der Minutenschleife der Erinnerungen: zur eingestellten Zeit senden.
    Nachgeholt wird höchstens eine halbe Stunde, nicht Stunden später."""
    cfg = config()
    if not cfg["targets"] or now.weekday() != cfg["weekday"]:
        return
    hour, minute = map(int, cfg["at"].split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not 0 <= (now - target).total_seconds() < 1800:
        return
    week = (now.date() - timedelta(days=now.weekday())).isoformat()
    send_all(now, week_key=week)
