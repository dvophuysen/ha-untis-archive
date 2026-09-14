"""Log into the IServ web portal and find the feeds it offers.

CalDAV turned out to be an empty house at this school: every collection the
child can reach answers but holds nothing, while the subscribed exam feeds in
Home Assistant demonstrably carry appointments. Those feeds come from a module
of the portal, not from the calendar store, so the address has to be read off
the portal itself.

Credentials stay inside this module. What leaves it are addresses and link
captions, never page bodies.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from .iserv_connector import IservLoginError, _LoginForm, _looks_like_login

_LOGGER = logging.getLogger("schul_cockpit.calendar")

MAX_BYTES = 4 * 1024 * 1024
MAX_PAGES = 24
# The desktop only links what the user has pinned, so the modules that can
# carry dates are visited by name as well.
SEEDS = ("iserv/", "iserv/calendar/", "iserv/exam/", "iserv/exam/schedule/",
         "iserv/plan/", "iserv/timetable/", "iserv/substitution/", "iserv/booking/")
# Modules that can hold dates: calendar, exam plan, substitutions, timetable.
_INTERESTING = re.compile(r"(calendar|kalender|exam|klausur|klausel|termin|plan|ics|ical|subscri|abonn)", re.I)


class _Links(HTMLParser):
    """Every link and its caption, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict] = []
        self._open: dict | None = None
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "a" and values.get("href"):
            self._open = {"href": values["href"], "text": "",
                          "title": (values.get("title") or "")[:120]}
            self.links.append(self._open)
        elif tag in ("input", "textarea") and values.get("value", "").startswith("http"):
            # Subscription addresses often sit in a read-only field, not a link.
            self.links.append({"href": values["value"], "text": "(Feld)", "title": ""})

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "a":
            self._open = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()
        elif self._open is not None and len(self._open["text"]) < 120:
            self._open["text"] += data.strip()


def _same_host(url: str, portal_url: str) -> bool:
    return urlsplit(url).hostname == urlsplit(portal_url).hostname


async def login(portal_url: str, username: str, password: str) -> httpx.AsyncClient:
    """An authenticated portal session. The caller closes it."""
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True,
        headers={"User-Agent": "Schul-Cockpit school calendar"})
    try:
        landing = await client.get(urljoin(portal_url + "/", "iserv/"))
        landing.raise_for_status()
        form = _LoginForm()
        form.feed(landing.text)
        if form.action is None or "_password" not in form.fields:
            raise IservLoginError("Die IServ-Anmeldeseite wurde nicht erkannt")
        data = dict(form.fields)
        data["_username"] = username
        data["_password"] = password
        if "_remember_me" in data:
            data["_remember_me"] = "on"
        login_url = urljoin(str(landing.url), form.action)
        if not _same_host(login_url, portal_url):
            raise IservLoginError("IServ verweist auf eine unerwartete Anmeldung")
        answer = await client.post(login_url, data=data)
        answer.raise_for_status()
        if _looks_like_login(str(answer.url), answer.text):
            raise IservLoginError("Benutzername oder Passwort stimmen nicht")
    except httpx.HTTPError as exc:
        await client.aclose()
        raise IservLoginError("IServ ist gerade nicht erreichbar") from exc
    except Exception:
        await client.aclose()
        raise
    return client


async def _page(client: httpx.AsyncClient, url: str) -> tuple[int, _Links]:
    parser = _Links()
    try:
        answer = await client.get(url)
    except httpx.HTTPError:
        return 0, parser
    if answer.status_code < 400 and len(answer.content) <= MAX_BYTES:
        if "html" in answer.headers.get("content-type", ""):
            parser.feed(answer.text)
    return answer.status_code, parser


async def survey(portal_url: str, username: str, password: str) -> dict:
    """Which date-carrying modules the portal offers, and their feed addresses."""
    base = portal_url.rstrip("/") + "/"
    pages: list[dict] = []
    feeds: list[dict] = []
    seen: set[str] = set()
    client = await login(portal_url, username, password)
    try:
        queue = [urljoin(base, path) for path in SEEDS]
        while queue and len(pages) < MAX_PAGES:
            url = queue.pop(0)
            if url in seen or not _same_host(url, portal_url):
                continue
            seen.add(url)
            status, parser = await _page(client, url)
            interesting = []
            for link in parser.links:
                target = urljoin(url, link["href"])
                if not _same_host(target, portal_url):
                    continue
                label = f"{link['text']} {link['title']} {target}"
                if not _INTERESTING.search(label):
                    continue
                interesting.append({"href": target, "text": link["text"][:80]})
                if re.search(r"(\.ics|/ical|/ics)", target, re.I):
                    if target not in {f["href"] for f in feeds}:
                        feeds.append({"href": target, "text": link["text"][:80], "gefunden_auf": url})
                elif len(seen) + len(queue) < MAX_PAGES and target not in seen:
                    queue.append(target)
            pages.append({"url": url, "status": status, "titel": parser.title[:120],
                          "links_gesamt": len(parser.links),
                          "anmeldeseite": any(l["href"].endswith("/auth/login") for l in parser.links)
                          or "login" in parser.title.casefold(),
                          "treffer": interesting[:25]})
    finally:
        await client.aclose()
    return {"seiten": pages, "feeds": feeds}


async def read_feed(portal_url: str, username: str, password: str, url: str) -> str:
    """The raw iCalendar text behind a portal address."""
    if not _same_host(url, portal_url):
        raise IservLoginError("Diese Adresse gehört nicht zu eurem IServ")
    client = await login(portal_url, username, password)
    try:
        answer = await client.get(url)
        answer.raise_for_status()
    except httpx.HTTPError as exc:
        raise IservLoginError("Der Kalender konnte nicht geladen werden") from exc
    finally:
        await client.aclose()
    if len(answer.content) > MAX_BYTES:
        raise IservLoginError("Die Kalenderdatei ist unerwartet groß")
    text = answer.text
    if "BEGIN:VCALENDAR" not in text:
        raise IservLoginError("Unter dieser Adresse steht kein Kalender")
    return text
