"""Read school calendars straight from IServ over CalDAV.

Home Assistant's remote_calendar drops a whole feed when IServ writes
``TZID=+02:00`` instead of a timezone name, and the school regenerates the
calendars every year while spreading exams over several of them. Reading the
collections ourselves removes both problems: we tolerate the malformed zone
and we rediscover the collections on every run instead of pinning an id.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx

_LOGGER = logging.getLogger("schul_cockpit.calendar")

DAV = "DAV:"
CAL = "urn:ietf:params:xml:ns:caldav"
APPLE = "http://apple.com/ns/ical/"
MAX_BYTES = 8 * 1024 * 1024
BERLIN = "Europe/Berlin"


class IservCalendarError(RuntimeError):
    pass


def _client(username: str, password: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        auth=(username, password),
        headers={"User-Agent": "Schul-Cockpit school calendar", "Content-Type": "application/xml; charset=utf-8"},
    )


def _root(portal_url: str) -> str:
    parsed = urlsplit(portal_url)
    return f"https://{parsed.hostname}/caldav/"


async def _propfind(client: httpx.AsyncClient, url: str, body: str, depth: str) -> ElementTree.Element:
    try:
        answer = await client.request("PROPFIND", url, content=body.encode(), headers={"Depth": depth})
    except httpx.HTTPError as exc:
        raise IservCalendarError("IServ ist gerade nicht erreichbar") from exc
    if answer.status_code in (401, 403):
        raise IservCalendarError("Benutzername oder Passwort stimmen nicht")
    if answer.status_code >= 400:
        raise IservCalendarError("IServ hat die Kalenderabfrage abgelehnt")
    if len(answer.content) > MAX_BYTES:
        raise IservCalendarError("Die Kalenderantwort ist unerwartet groß")
    try:
        return ElementTree.fromstring(answer.content)
    except ElementTree.ParseError as exc:
        raise IservCalendarError("Die Kalenderantwort war nicht lesbar") from exc


def _text(node, path: str) -> str:
    found = node.find(path)
    return (found.text or "").strip() if found is not None and found.text else ""


async def discover(portal_url: str, username: str, password: str) -> list[dict]:
    """Every calendar this account can see, freshly looked up each time."""
    root = _root(portal_url)
    async with _client(username, password) as client:
        principal = await _propfind(client, root, (
            '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
        ), "0")
        href = _text(principal, f".//{{{DAV}}}current-user-principal/{{{DAV}}}href") or root
        home_doc = await _propfind(client, urljoin(root, href), (
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:prop><c:calendar-home-set/></d:prop></d:propfind>"
        ), "0")
        home = _text(home_doc, f".//{{{CAL}}}calendar-home-set/{{{DAV}}}href") or href
        listing = await _propfind(client, urljoin(root, home), (
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
            'xmlns:a="http://apple.com/ns/ical/"><d:prop>'
            "<d:resourcetype/><d:displayname/><a:calendar-color/>"
            "<c:supported-calendar-component-set/></d:prop></d:propfind>"
        ), "1")

    found: list[dict] = []
    for response in listing.findall(f"{{{DAV}}}response"):
        resource = response.find(f".//{{{DAV}}}resourcetype")
        if resource is None or resource.find(f"{{{CAL}}}calendar") is None:
            continue
        components = {c.get("name") for c in response.findall(f".//{{{CAL}}}comp")}
        if components and "VEVENT" not in components:
            continue
        path = _text(response, f"{{{DAV}}}href")
        if not path:
            continue
        found.append({
            "url": urljoin(root, path),
            "name": _text(response, f".//{{{DAV}}}displayname") or path.rstrip("/").rsplit("/", 1)[-1],
            "color": (_text(response, f".//{{{APPLE}}}calendar-color") or "")[:9],
        })
    if not found:
        raise IservCalendarError("Es wurden keine Kalender gefunden")
    return sorted(found, key=lambda c: c["name"].casefold())


# IServ writes an offset where the standard demands a named zone. Home
# Assistant discards the whole file over this; we simply correct it.
_BAD_TZID = re.compile(r"TZID=([+-]\d{2}:?\d{2})(?=[:;])")


def repair_ics(text: str) -> str:
    return _BAD_TZID.sub(f"TZID={BERLIN}", text)


def _as_datetime(value, end=False) -> tuple[str, str | None]:
    """Return (YYYY-MM-DD, HH:MM or None) in local school time."""
    if isinstance(value, datetime):
        moment = value.astimezone(_zone()) if value.tzinfo else value
        return moment.date().isoformat(), moment.strftime("%H:%M")
    if isinstance(value, date):
        # An all-day end date is exclusive in iCalendar.
        day = value - timedelta(days=1) if end else value
        return day.isoformat(), None
    return "", None


def _zone():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(BERLIN)
    except Exception:
        return timezone.utc


def parse_events(ics_text: str, start: date, end: date) -> list[dict]:
    """Events of one calendar inside the window, malformed zones included."""
    from icalendar import Calendar

    events: list[dict] = []
    for block in ics_text.split("BEGIN:VCALENDAR"):
        if "BEGIN:VEVENT" not in block:
            continue
        try:
            calendar = Calendar.from_ical("BEGIN:VCALENDAR" + block)
        except Exception:
            continue
        for component in calendar.walk("VEVENT"):
            try:
                begins = component.decoded("DTSTART")
            except Exception:
                continue
            try:
                finishes = component.decoded("DTEND")
            except Exception:
                finishes = begins
            start_day, start_time = _as_datetime(begins)
            end_day, end_time = _as_datetime(finishes, end=True)
            if not start_day or start_day > end.isoformat() or (end_day or start_day) < start.isoformat():
                continue
            events.append({
                "uid": str(component.get("UID") or "")[:200],
                "summary": str(component.get("SUMMARY") or "").strip()[:300],
                "description": str(component.get("DESCRIPTION") or "").strip()[:2000],
                "location": str(component.get("LOCATION") or "").strip()[:200],
                "start_date": start_day,
                "end_date": end_day or start_day,
                "start_time": start_time,
                "end_time": end_time,
                "all_day": start_time is None,
                "recurring": bool(component.get("RRULE")),
            })
    return events


async def fetch(portal_url: str, username: str, password: str, calendar_url: str,
                start: date, end: date) -> list[dict]:
    """Events of one calendar; the server expands repetitions where it can."""
    window = (
        f'<c:time-range start="{start.strftime("%Y%m%dT000000Z")}" '
        f'end="{end.strftime("%Y%m%dT235959Z")}"/>'
    )
    query = (
        '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop>'
        f"<c:calendar-data><c:expand start=\"{start.strftime('%Y%m%dT000000Z')}\" "
        f"end=\"{end.strftime('%Y%m%dT235959Z')}\"/></c:calendar-data></d:prop>"
        f"<c:filter><c:comp-filter name=\"VCALENDAR\"><c:comp-filter name=\"VEVENT\">{window}"
        "</c:comp-filter></c:comp-filter></c:filter></c:calendar-query>"
    )
    plain = query.replace(
        f"<c:calendar-data><c:expand start=\"{start.strftime('%Y%m%dT000000Z')}\" "
        f"end=\"{end.strftime('%Y%m%dT235959Z')}\"/></c:calendar-data>", "<c:calendar-data/>")
    async with _client(username, password) as client:
        for body in (query, plain):
            try:
                answer = await client.request("REPORT", calendar_url, content=body.encode(),
                                              headers={"Depth": "1"})
            except httpx.HTTPError as exc:
                raise IservCalendarError("IServ ist gerade nicht erreichbar") from exc
            if answer.status_code < 400:
                break
            if answer.status_code in (401, 403):
                raise IservCalendarError("Benutzername oder Passwort stimmen nicht")
        else:
            raise IservCalendarError("IServ hat die Terminabfrage abgelehnt")
    try:
        document = ElementTree.fromstring(answer.content)
    except ElementTree.ParseError as exc:
        raise IservCalendarError("Die Terminantwort war nicht lesbar") from exc
    events: list[dict] = []
    for node in document.iter(f"{{{CAL}}}calendar-data"):
        if node.text:
            events.extend(parse_events(repair_ics(node.text), start, end))
    unique: dict[tuple, dict] = {}
    for event in events:
        unique[(event["uid"], event["start_date"], event["start_time"])] = event
    return sorted(unique.values(), key=lambda e: (e["start_date"], e["start_time"] or ""))
