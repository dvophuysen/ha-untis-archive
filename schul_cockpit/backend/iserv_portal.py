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

import json
import logging
import re
from datetime import date, datetime
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


_COLLECT_SCRIPT = r"""
const out = {links: [], fields: [], text: (document.body ? document.body.innerText : '').slice(0, 4000),
             abrufe: performance.getEntriesByType('resource')
               .map(e => e.name)
               .filter(n => /(api|json|event|termin|feed|ics)/i.test(n) && !/\.(css|js|png|jpg|svg|woff2?)(\?|$)/i.test(n))
               .slice(0, 40)};
const seen = new Set();
for (const a of document.querySelectorAll('a[href]')) {
  const href = a.href || '';
  if (!href || seen.has(href)) continue;
  seen.add(href);
  out.links.push({href, text: (a.innerText || a.getAttribute('title') || '').trim().slice(0, 90)});
}
for (const i of document.querySelectorAll('input,textarea')) {
  const value = (i.value || '').trim();
  if (value.startsWith('http')) out.fields.push({href: value, text: (i.name || i.id || 'Feld').slice(0, 60)});
}
return out;
"""


def _browse_sync(portal_url: str, username: str, password: str, paths: tuple[str, ...]) -> dict:
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    from .textbook_browser import _driver

    base = portal_url.rstrip("/") + "/"
    pages: list[dict] = []
    feeds: list[dict] = []
    driver = _driver()
    try:
        driver.get(urljoin(base, "iserv/"))
        driver.find_element(By.NAME, "_username").send_keys(username)
        driver.find_element(By.NAME, "_password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        try:
            WebDriverWait(driver, 20).until(lambda d: "/auth/login" not in d.current_url)
        except TimeoutException:
            raise IservLoginError("Benutzername oder Passwort stimmen nicht")
        for path in paths:
            url = urljoin(base, path)
            try:
                driver.get(url)
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script("return document.readyState") == "complete")
            except Exception:
                pages.append({"url": url, "fehler": "nicht geladen"})
                continue
            # The portal renders itself; without this pause the body is empty.
            WebDriverWait(driver, 15).until(
                lambda d: len(d.execute_script("return document.body ? document.body.innerText : ''")) > 40
                or d.execute_script("return document.querySelectorAll('a[href]').length") > 6)
            data = driver.execute_script(_COLLECT_SCRIPT)
            treffer = []
            for entry in data["links"] + data["fields"]:
                if not _same_host(entry["href"], portal_url):
                    continue
                label = f"{entry['text']} {entry['href']}"
                if re.search(r"(\.ics|/ical|webcal|subscri|abonn)", label, re.I):
                    if entry["href"] not in {f["href"] for f in feeds}:
                        feeds.append({**entry, "gefunden_auf": url})
                elif _INTERESTING.search(label):
                    treffer.append(entry)
            pages.append({"url": url, "titel": driver.title[:120],
                          "adresse": driver.current_url[:200],
                          "abrufe": data.get("abrufe", []),
                          "text": data["text"][:900],
                          "links_gesamt": len(data["links"]),
                          "treffer": treffer[:30]})
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return {"seiten": pages, "feeds": feeds}


async def browse(portal_url: str, username: str, password: str,
                 paths: tuple[str, ...] = SEEDS) -> dict:
    """The same survey with a real browser.

    Current IServ ships a rendered application: fetching the HTML returns a
    skeleton with four links, so the modules only become visible once the page
    has actually run.
    """
    import asyncio

    return await asyncio.to_thread(_browse_sync, portal_url, username, password, paths)


_FETCH_SCRIPT = r"""
const done = arguments[arguments.length - 1];
const paths = arguments[0];
(async () => {
  const out = [];
  for (const path of paths) {
    try {
      const answer = await fetch(path, {credentials: 'same-origin', headers: {'Accept': 'application/json, text/calendar, */*'}});
      const text = await answer.text();
      out.push({pfad: path, status: answer.status, typ: answer.headers.get('content-type') || '', text: text.slice(0, 120000)});
    } catch (error) {
      out.push({pfad: path, status: 0, fehler: String(error).slice(0, 200)});
    }
  }
  done(out);
})();
"""


def _read_sync(portal_url: str, username: str, password: str, paths: tuple[str, ...]) -> list[dict]:
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    from .textbook_browser import _driver

    base = portal_url.rstrip("/") + "/"
    driver = _driver()
    try:
        driver.get(urljoin(base, "iserv/"))
        driver.find_element(By.NAME, "_username").send_keys(username)
        driver.find_element(By.NAME, "_password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        try:
            WebDriverWait(driver, 20).until(lambda d: "/auth/login" not in d.current_url)
        except TimeoutException:
            raise IservLoginError("Benutzername oder Passwort stimmen nicht")
        # The request has to come from the page itself, so the session applies.
        driver.get(urljoin(base, "iserv/calendar"))
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete")
        driver.set_script_timeout(120)
        return driver.execute_async_script(_FETCH_SCRIPT, list(paths))
    finally:
        try:
            driver.quit()
        except Exception:
            pass


async def read(portal_url: str, username: str, password: str, paths: tuple[str, ...]) -> list[dict]:
    """Ask the portal's own data addresses, from inside the logged-in page."""
    import asyncio

    for path in paths:
        if path.startswith("http") and not _same_host(path, portal_url):
            raise IservLoginError("Diese Adresse gehört nicht zu eurem IServ")
    return await asyncio.to_thread(_read_sync, portal_url, username, password, paths)


PLUGIN_MARK = "/calendar4/plugin?plugin="


def is_plugin(url: str) -> bool:
    return PLUGIN_MARK in url


async def _json(client: httpx.AsyncClient, url: str):
    try:
        answer = await client.get(url, headers={"Accept": "application/json"})
        answer.raise_for_status()
    except httpx.HTTPError as exc:
        raise IservLoginError("IServ hat die Terminabfrage abgelehnt") from exc
    if len(answer.content) > MAX_BYTES:
        raise IservLoginError("Die Terminantwort ist unerwartet groß")
    try:
        return answer.json()
    except ValueError:
        raise IservLoginError("Die Terminantwort war nicht lesbar") from None


async def portal_json(portal_url: str, username: str, password: str,
                      paths: tuple[str, ...]) -> dict[str, object]:
    """JSON from the portal's own addresses, whatever it takes.

    The calendar application answers its own interface only to a session the
    running page holds; a plain login gets 401 there. So the cheap way is tried
    first and the browser takes over for whatever is left.
    """
    base = portal_url.rstrip("/") + "/"
    # The browser resolves against the page it sits on, so it needs the full
    # address; the caller gets its own spelling back either way.
    targets = {urljoin(base, path): path for path in paths}
    results: dict[str, object] = {}
    missing: list[str] = []
    client = await login(portal_url, username, password)
    try:
        for url, path in targets.items():
            try:
                results[path] = await _json(client, url)
            except IservLoginError:
                missing.append(url)
    finally:
        await client.aclose()
    if missing:
        for entry in await read(portal_url, username, password, tuple(missing)):
            path = targets.get(entry.get("pfad", ""))
            if path is None:
                continue
            if entry.get("status") != 200 or not entry.get("text"):
                _LOGGER.warning("Portal antwortet auf %s mit %s", path, entry.get("status"))
                continue
            try:
                results[path] = json.loads(entry["text"])
            except ValueError:
                _LOGGER.warning("Portalantwort nicht lesbar: %s", path)
    return results


async def sources(portal_url: str, username: str, password: str) -> list[dict]:
    """The calendar module's own list of sources, plugins included.

    Exam dates at this school are a plugin of the calendar, not a collection,
    so CalDAV cannot see them at all.
    """
    base = portal_url.rstrip("/") + "/"
    path = "iserv/calendar/api/eventsources"
    data = (await portal_json(portal_url, username, password, (path,))).get(path)
    found = []
    for entry in data if isinstance(data, list) else []:
        url = urljoin(base, str(entry.get("url") or ""))
        if entry.get("type") != "plugin" or not is_plugin(url) or not _same_host(url, portal_url):
            continue
        found.append({"url": url, "name": str(entry.get("label") or entry.get("id") or "Plugin")[:80],
                      "id": str(entry.get("id") or ""), "color": str(entry.get("color") or "")[:9]})
    return found


def _split(value: str | None) -> tuple[str, str | None]:
    """An ISO moment as a local date and, unless all day, a time."""
    if not value:
        return "", None
    moment = datetime.fromisoformat(value)
    return moment.date().isoformat(), moment.strftime("%H:%M")


def _window(url: str, start: date, end: date) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}start={start.isoformat()}&end={end.isoformat()}"


async def plugin_events(portal_url: str, username: str, password: str, url: str,
                        start: date, end: date) -> list[dict]:
    """Events of one calendar plugin, in the shape the store expects."""
    if not is_plugin(url) or not _same_host(url, portal_url):
        raise IservLoginError("Diese Adresse gehört nicht zu eurem IServ")
    full = _window(url, start, end)
    data = (await portal_json(portal_url, username, password, (full,))).get(full)
    return parse_plugin(data, start, end)


def parse_plugin(data, start: date, end: date) -> list[dict]:
    """Plugin entries as calendar events."""
    events: list[dict] = []
    for entry in data if isinstance(data, list) else []:
        first, first_time = _split(entry.get("start"))
        last, last_time = _split(entry.get("end") or entry.get("start"))
        if not first:
            continue
        all_day = bool(entry.get("allDay"))
        fields = entry.get("displayFields") or []
        note = " · ".join(
            f"{f.get('label')}: {f.get('text')}" for f in fields
            if isinstance(f, dict) and f.get("text"))
        events.append({
            "uid": str(entry.get("id") or f"{first}-{entry.get('title')}")[:200],
            "summary": str(entry.get("title") or "Termin")[:300],
            "description": note[:500],
            "location": str(entry.get("location") or "")[:200],
            "start_date": first,
            "end_date": last or first,
            "start_time": None if all_day else first_time,
            "end_time": None if all_day else last_time,
            "all_day": all_day,
        })
    return [e for e in events if e["start_date"] <= end.isoformat() and e["end_date"] >= start.isoformat()]
