"""Stored school calendars per child, their roles and their events.

The school rebuilds its calendars every year and spreads exams over several
of them, so nothing here may depend on a fixed address. Discovery runs again
on every sync, and a role follows the calendar's name when its address
changes.
"""

from __future__ import annotations

import logging
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

from . import iserv_calendar, iserv_portal
from .db import webapp_conn
from .iserv_calendar import IservCalendarError
from .iserv_connector import IservLoginError
from .secret_store import decrypt_secret

_LOGGER = logging.getLogger("schul_cockpit.calendar")

ROLES = ("exam", "lessons", "other", "unused")
PAST_DAYS = 30
AHEAD_DAYS = 400
# A plugin whose purpose is obvious should not wait for a decision: the exam
# plan is why this exists, holidays and set work are context.
DEFAULT_ROLES = {"exam-plan": "exam", "holiday": "other", "exercise": "other"}


def _default_role(entry: dict) -> str:
    key = entry.get("url", "").rsplit("plugin=", 1)[-1]
    return DEFAULT_ROLES.get(key, "unused")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def credentials(account_id: int):
    with closing(webapp_conn()) as conn:
        return conn.execute(
            "SELECT portal_url,username,password_ciphertext FROM digital_textbook_credentials "
            "WHERE account_id=?", (account_id,)).fetchone()


def calendars(account_id: int) -> list[dict]:
    with closing(webapp_conn()) as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM iserv_calendar_events e WHERE e.calendar_id=c.id) AS events "
            "FROM iserv_calendars c WHERE c.account_id=? ORDER BY c.role!='exam', lower(c.name)",
            (account_id,)).fetchall()
        return [dict(r) for r in rows]


def state(account_id: int) -> dict:
    with closing(webapp_conn()) as conn:
        row = conn.execute("SELECT * FROM iserv_calendar_sync WHERE account_id=?", (account_id,)).fetchone()
    return dict(row) if row else {"account_id": account_id, "status": "pending", "error": None,
                                  "calendars": 0, "events": 0, "synced_at": None}


def set_role(account_id: int, calendar_id: int, role: str) -> bool:
    if role not in ROLES:
        raise ValueError("Unbekannte Rolle")
    with closing(webapp_conn()) as conn, conn:
        return bool(conn.execute("UPDATE iserv_calendars SET role=? WHERE id=? AND account_id=?",
                                 (role, calendar_id, account_id)).rowcount)


def _remember(conn, account_id: int, found: list[dict]) -> dict[str, int]:
    """Store the discovered calendars and carry roles over a yearly rebuild."""
    stamp = now_iso()
    known = {r["url"]: dict(r) for r in conn.execute(
        "SELECT id,url,name,role FROM iserv_calendars WHERE account_id=?", (account_id,))}
    by_name = {r["name"].casefold(): r for r in known.values() if r["role"] != "unused"}
    seen: dict[str, int] = {}
    for entry in found:
        row = known.get(entry["url"])
        role = row["role"] if row else None
        if role is None:
            # A new address with a familiar name is last year's calendar
            # rebuilt; keep what the parents decided about it.
            previous = by_name.get(entry["name"].casefold())
            role = previous["role"] if previous else _default_role(entry)
        conn.execute(
            "INSERT INTO iserv_calendars(account_id,url,name,color,role,last_seen,missing_since,created_at) "
            "VALUES(?,?,?,?,?,?,NULL,?) ON CONFLICT(account_id,url) DO UPDATE SET "
            "name=excluded.name,color=excluded.color,last_seen=excluded.last_seen,missing_since=NULL",
            (account_id, entry["url"], entry["name"], entry.get("color"), role, stamp, stamp))
        seen[entry["url"]] = conn.execute(
            "SELECT id FROM iserv_calendars WHERE account_id=? AND url=?",
            (account_id, entry["url"])).fetchone()[0]
    if seen:
        marks = ",".join("?" * len(seen))
        conn.execute(
            f"UPDATE iserv_calendars SET missing_since=COALESCE(missing_since,?) "
            f"WHERE account_id=? AND url NOT IN ({marks})", (stamp, account_id, *seen))
    return seen


async def sync(account_id: int, *, past_days: int = PAST_DAYS, ahead_days: int = AHEAD_DAYS) -> dict:
    """Rediscover the calendars and refresh the events of the used ones."""
    row = credentials(account_id)
    if row is None:
        raise IservCalendarError("Für dieses Kind ist noch kein IServ-Zugang gespeichert")
    password = decrypt_secret(row["password_ciphertext"])
    try:
        found = await iserv_calendar.discover(row["portal_url"], row["username"], password)
        try:
            # The exam plan is a plugin of the calendar module, invisible to
            # CalDAV. Without it the collections alone stay empty all year.
            found = found + await iserv_portal.sources(
                row["portal_url"], row["username"], password)
        except IservLoginError as exc:
            _LOGGER.warning("Kalender-Plugins nicht gelesen: %s", exc)
        with closing(webapp_conn()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            ids = _remember(conn, account_id, found)
            wanted = {r["url"]: r["id"] for r in conn.execute(
                "SELECT url,id FROM iserv_calendars WHERE account_id=? AND role IN ('exam','lessons','other')",
                (account_id,))}
        today = date.today()
        start, end = today - timedelta(days=past_days), today + timedelta(days=ahead_days)
        total = 0
        kept: list[int] = []
        live = {url: cid for url, cid in wanted.items() if url in ids}
        # Every plugin in one go: each fall back to the browser costs a session.
        plugins = {iserv_portal._window(url, start, end): cid
                   for url, cid in live.items() if iserv_portal.is_plugin(url)}
        if plugins:
            answers = await iserv_portal.portal_json(
                row["portal_url"], row["username"], password, tuple(plugins))
            for full, calendar_id in plugins.items():
                # Nur eine echte Liste, auch eine leere, ersetzt den Stand.
                # Fehlt die Antwort (Fehlerstatus, leerer oder unlesbarer
                # Text), bleiben die Termine stehen: Bis 1.31.2 löschte ein
                # gestörter Abruf den ganzen Klausurplan im Fenster.
                data = answers.get(full)
                if not isinstance(data, list):
                    kept.append(calendar_id)
                    continue
                events = iserv_portal.parse_plugin(data, start, end)
                total += _store_events(account_id, calendar_id, events, start, end)
        for url, calendar_id in live.items():
            if iserv_portal.is_plugin(url):
                continue
            events = await iserv_calendar.fetch(row["portal_url"], row["username"], password, url, start, end)
            total += _store_events(account_id, calendar_id, events, start, end)
    except (IservCalendarError, IservLoginError) as exc:
        _record(account_id, "failed", str(exc), 0, 0)
        raise IservCalendarError(str(exc)) from None
    except Exception as exc:
        _record(account_id, "failed", type(exc).__name__, 0, 0)
        raise IservCalendarError("Die Kalender konnten nicht gelesen werden") from None
    finally:
        password = ""
    # Teilweise gelesen bleibt „ready“ (andere Zustände kennt die Anzeige
    # nicht); der Fehlertext sagt, welcher Stand nicht erneuert wurde.
    note = f"{len(kept)} Kalender nicht erreichbar, bisherige Termine bleiben" if kept else None
    if kept:
        _LOGGER.warning("Kalender-Plugins ohne Antwort, Stand behalten: %s", kept)
    _record(account_id, "ready", note, len(found), total)
    return state(account_id)


def _store_events(account_id: int, calendar_id: int, events: list[dict], start: date, end: date) -> int:
    stamp = now_iso()
    with closing(webapp_conn()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        # Replace the window wholesale: a cancelled exam has to disappear.
        conn.execute("DELETE FROM iserv_calendar_events WHERE account_id=? AND calendar_id=? "
                     "AND start_date>=? AND start_date<=?",
                     (account_id, calendar_id, start.isoformat(), end.isoformat()))
        for event in events:
            conn.execute(
                "INSERT OR REPLACE INTO iserv_calendar_events(account_id,calendar_id,uid,summary,description,"
                "location,start_date,end_date,start_time,end_time,all_day,fetched_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (account_id, calendar_id, event["uid"], event["summary"], event["description"],
                 event["location"], event["start_date"], event["end_date"], event["start_time"],
                 event["end_time"], int(event["all_day"]), stamp))
    return len(events)


def _record(account_id: int, status: str, error: str | None, found: int, events: int) -> None:
    with closing(webapp_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO iserv_calendar_sync(account_id,status,error,calendars,events,synced_at) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET status=excluded.status,"
            "error=excluded.error,calendars=excluded.calendars,events=excluded.events,synced_at=excluded.synced_at",
            (account_id, status, (error or "")[:200] or None, found, events, now_iso()))


def events(account_id: int, start: str, end: str, *, role: str | None = "exam") -> list[dict]:
    """Stored events of the calendars in that role, several calendars merged."""
    where = ["e.account_id=?", "e.start_date<=?", "e.end_date>=?"]
    args: list = [account_id, end, start]
    if role:
        where.append("c.role=?")
        args.append(role)
    with closing(webapp_conn()) as conn:
        rows = conn.execute(
            "SELECT e.*, c.name AS calendar_name, c.role FROM iserv_calendar_events e "
            "JOIN iserv_calendars c ON c.id=e.calendar_id WHERE " + " AND ".join(where) +
            " ORDER BY e.start_date, COALESCE(e.start_time,'')", tuple(args)).fetchall()
    merged: dict[tuple, dict] = {}
    for row in rows:
        # The same exam can sit in two calendars; one entry is enough.
        merged.setdefault((row["summary"].casefold(), row["start_date"], row["start_time"]), dict(row))
    return list(merged.values())


def configured_accounts() -> list[int]:
    with closing(webapp_conn()) as conn:
        return [r[0] for r in conn.execute(
            "SELECT account_id FROM digital_textbook_credentials ORDER BY account_id")]
