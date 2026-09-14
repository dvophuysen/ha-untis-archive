"""IServ login verification used before accessing licensed school media."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx


class IservLoginError(RuntimeError):
    pass


class _LoginForm(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._inside = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "form" and (
            "login" in (values.get("action") or "").lower()
            or self.action is None
        ):
            self.action = values.get("action") or ""
            self._inside = True
        elif tag == "input" and self._inside and values.get("name"):
            self.fields[values["name"]] = values.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._inside:
            self._inside = False


def _looks_like_login(url: str, html: str) -> bool:
    lower = html.lower()
    return (
        "/auth/login" in urlsplit(url).path.lower()
        or ('name="_password"' in lower and 'name="_username"' in lower)
    )


async def verify_iserv_login(portal_url: str, username: str, password: str) -> None:
    """Log in and confirm that the Eduplaces connector is reachable.

    No cookies or page bodies leave this function. A fresh client is discarded
    after every check, so verification never creates a reusable browser session.
    """
    timeout = httpx.Timeout(25.0, connect=10.0)
    headers = {"User-Agent": "Schul-Cockpit/0.35 textbook access check"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        try:
            landing = await client.get(urljoin(portal_url + "/", "iserv/"))
            landing.raise_for_status()
        except httpx.HTTPError as exc:
            raise IservLoginError("IServ ist gerade nicht erreichbar") from exc

        parser = _LoginForm()
        parser.feed(landing.text)
        if not parser.action or "_password" not in parser.fields:
            raise IservLoginError("Die IServ-Anmeldeseite wurde nicht erkannt")

        data = dict(parser.fields)
        data["_username"] = username
        data["_password"] = password
        if "_remember_me" in data:
            data["_remember_me"] = "on"
        login_url = urljoin(str(landing.url), parser.action)
        if urlsplit(login_url).hostname != urlsplit(portal_url).hostname:
            raise IservLoginError("IServ verweist auf eine unerwartete Anmeldung")
        try:
            result = await client.post(login_url, data=data)
            result.raise_for_status()
        except httpx.HTTPError as exc:
            raise IservLoginError("Anmeldung bei IServ fehlgeschlagen") from exc
        if _looks_like_login(str(result.url), result.text):
            raise IservLoginError("Benutzername oder Passwort stimmen nicht")

        try:
            connector = await client.get(urljoin(portal_url + "/", "iserv/eduplacesconnector/"))
            connector.raise_for_status()
        except httpx.HTTPError as exc:
            raise IservLoginError("IServ ist erreichbar, aber Eduplaces konnte nicht geöffnet werden") from exc
        if _looks_like_login(str(connector.url), connector.text):
            raise IservLoginError("Die Anmeldung ist nicht aktiv geblieben")
