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
MAX_HOMES = 30
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


def _name(response, path: str, owner: str) -> str:
    """A readable calendar name.

    IServ names a group calendar "<Gruppe> Calendar" and does not always
    update it when the group is renamed, so the group itself is the better
    label; only a calendar named differently keeps its own name.
    """
    own = _text(response, f".//{{{DAV}}}displayname")
    fallback = path.rstrip("/").rsplit("/", 1)[-1] if path else "Kalender"
    if owner and (not own or own.casefold() in (f"{owner} calendar".casefold(), "calendar", "kalender")):
        return owner
    if owner and own.casefold().endswith(" calendar"):
        return owner
    return own or owner or fallback


async def discover(portal_url: str, username: str, password: str) -> list[dict]:
    """Every calendar this account can see, freshly looked up each time.

    IServ answers the home-set with one principal per shared group, and each
    principal keeps its calendar one level below. Following only the first
    one finds the child's own calendar and none of the class calendars.
    """
    root = _root(portal_url)
    found: list[dict] = []
    async with _client(username, password) as client:
        principal = await _propfind(client, root, (
            '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
        ), "0")
        href = _text(principal, f".//{{{DAV}}}current-user-principal/{{{DAV}}}href") or root
        home_doc = await _propfind(client, urljoin(root, href), (
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            "<d:prop><c:calendar-home-set/><d:group-membership/></d:prop></d:propfind>"
        ), "0")
        homes = list(dict.fromkeys(
            [node.text for node in home_doc.iter(f"{{{DAV}}}href") if node.text] or [href]))
        seen: set[str] = set()
        for home in homes[:MAX_HOMES]:
            try:
                listing = await _propfind(client, urljoin(root, home), (
                    '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
                    'xmlns:a="http://apple.com/ns/ical/"><d:prop>'
                    "<d:resourcetype/><d:displayname/><a:calendar-color/>"
                    "<c:supported-calendar-component-set/></d:prop></d:propfind>"
                ), "1")
            except IservCalendarError:
                continue
            owner = ""
            for response in listing.findall(f"{{{DAV}}}response"):
                if _text(response, f"{{{DAV}}}href").rstrip("/") == home.rstrip("/"):
                    owner = _text(response, f".//{{{DAV}}}displayname")
            for response in listing.findall(f"{{{DAV}}}response"):
                resource = response.find(f".//{{{DAV}}}resourcetype")
                if resource is None or resource.find(f"{{{CAL}}}calendar") is None:
                    continue
                components = {c.get("name") for c in response.findall(f".//{{{CAL}}}comp")}
                if components and "VEVENT" not in components:
                    continue
                path = _text(response, f"{{{DAV}}}href")
                url = urljoin(root, path) if path else ""
                if not url or url in seen:
                    continue
                seen.add(url)
                found.append({"url": url, "name": _name(response, path, owner),
                              "color": (_text(response, f".//{{{APPLE}}}calendar-color") or "")[:9]})
    if not found:
        raise IservCalendarError("Es wurden keine Kalender gefunden")
    return sorted(found, key=lambda c: c["name"].casefold())


async def probe(portal_url: str, username: str, password: str) -> dict:
    """Everything the server reports about the account's collections.

    Only structure: addresses, display names and resource types. No event
    contents, no credentials. Used to work out where a server keeps shared
    calendars when discovery comes back thin.
    """
    root = _root(portal_url)
    steps: list[dict] = []

    def describe(document, label: str) -> list[dict]:
        rows = []
        for response in document.findall(f"{{{DAV}}}response"):
            resource = response.find(f".//{{{DAV}}}resourcetype")
            kinds = sorted(child.tag.split("}")[-1] for child in (resource or [])) if resource is not None else []
            rows.append({
                "href": _text(response, f"{{{DAV}}}href"),
                "name": _text(response, f".//{{{DAV}}}displayname"),
                "types": kinds,
            })
        steps.append({"schritt": label, "eintraege": rows[:60]})
        return rows

    async with _client(username, password) as client:
        principal = await _propfind(client, root, (
            '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/>'
            "<d:displayname/><d:resourcetype/></d:prop></d:propfind>"), "0")
        href = _text(principal, f".//{{{DAV}}}current-user-principal/{{{DAV}}}href") or root
        steps.append({"schritt": "principal", "eintraege": [{"href": href}]})

        home_doc = await _propfind(client, urljoin(root, href), (
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" '
            'xmlns:cs="http://calendarserver.org/ns/"><d:prop><c:calendar-home-set/>'
            "<cs:calendar-proxy-read-for/><cs:calendar-proxy-write-for/>"
            "<d:group-membership/></d:prop></d:propfind>"), "0")
        homes = [h.text for h in home_doc.iter(f"{{{DAV}}}href") if h.text]
        steps.append({"schritt": "home-set", "eintraege": [{"href": h} for h in homes[:20]]})

        for home in dict.fromkeys(homes or [href]):
            document = await _propfind(client, urljoin(root, home), (
                '<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:displayname/>'
                "</d:prop></d:propfind>"), "1")
            rows = describe(document, f"depth1 {home}")
            # One level further: some servers keep the calendars in folders.
            for row in rows[:12]:
                if row["href"] and row["href"].rstrip("/") != home.rstrip("/") and not row["types"]:
                    continue
                if row["href"] and "calendar" not in row["types"] and row["href"].rstrip("/") != home.rstrip("/"):
                    deeper = await _propfind(client, urljoin(root, row["href"]), (
                        '<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:displayname/>'
                        "</d:prop></d:propfind>"), "1")
                    describe(deeper, f"depth1 {row['href']}")
    return {"root": root, "schritte": steps}


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
