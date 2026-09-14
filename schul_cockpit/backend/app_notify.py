"""Reminders through the Home Assistant companion app.

Web push on iOS needed the app added to the home screen with an explicit push
permission, and Screen Time treats such a page as web content: during a
downtime it is blocked whatever the allow list says, and one of the phones in
this household stays on an iOS that will never get the newer Screen Time. The
companion app is a real app, can be allowed permanently, and carries ordinary
push notifications. So that is the transport.
"""

from __future__ import annotations

import logging
from contextlib import closing

import httpx

from .config import SETTINGS
from .db import webapp_conn

LOG = logging.getLogger("schul_cockpit.notify")

PREFIX = "mobile_app_"
TIMEOUT = 10.0


def _headers() -> dict[str, str]:
    if not SETTINGS.supervisor_token:
        raise RuntimeError("SUPERVISOR_TOKEN fehlt")
    return {"Authorization": f"Bearer {SETTINGS.supervisor_token}",
            "Content-Type": "application/json"}


def own_panel() -> str:
    """The path the notification should open: this add-on's own sidebar entry.

    An ingress address answers 404 when a notification opens it; the panel is
    registered under the add-on slug.
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            answer = client.get(f"{SETTINGS.supervisor_url}/addons/self/info", headers=_headers())
        answer.raise_for_status()
        slug = (answer.json().get("data") or {}).get("slug")
    except Exception:
        LOG.warning("Eigener Add-on-Slug nicht ermittelbar")
        return "/"
    return f"/{slug}" if slug else "/"


def services() -> list[str]:
    """Every companion-app target Home Assistant currently offers."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            answer = client.get(f"{SETTINGS.supervisor_url}/core/api/services", headers=_headers())
        answer.raise_for_status()
        for domain in answer.json():
            if domain.get("domain") == "notify":
                return sorted(name for name in (domain.get("services") or {})
                              if name.startswith(PREFIX))
    except Exception:
        LOG.warning("Mitteilungsdienste nicht abrufbar", exc_info=True)
    return []


def send(service: str, title: str, message: str, url: str) -> bool:
    """One notification. Tapping it opens `url`; buttons would need a long press
    and are therefore not part of the routine."""
    if not service.startswith(PREFIX) or "/" in service:
        raise ValueError("Unerwarteter Mitteilungsdienst")
    payload = {"title": title, "message": message,
               "data": {"url": url, "push": {"interruption-level": "active"}}}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            answer = client.post(f"{SETTINGS.supervisor_url}/core/api/services/notify/{service}",
                                 headers=_headers(), json=payload)
        return answer.status_code < 400
    except Exception:
        LOG.warning("Mitteilung an %s nicht zugestellt", service)
        return False


def targets(account_id: int) -> list[str]:
    with closing(webapp_conn()) as conn:
        return [r[0] for r in conn.execute(
            "SELECT service FROM reminder_app_targets WHERE account_id=? ORDER BY service",
            (account_id,))]


def set_targets(account_id: int, chosen: list[str]) -> list[str]:
    wanted = sorted({s for s in chosen if s.startswith(PREFIX) and "/" not in s})
    with closing(webapp_conn()) as conn, conn:
        conn.execute("DELETE FROM reminder_app_targets WHERE account_id=?", (account_id,))
        conn.executemany("INSERT INTO reminder_app_targets(account_id,service) VALUES(?,?)",
                         [(account_id, s) for s in wanted])
    return wanted
