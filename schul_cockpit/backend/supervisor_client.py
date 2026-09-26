"""Thin wrapper around the HA Supervisor's proxy to the Core REST API.

Auth is via the SUPERVISOR_TOKEN env var, which the Supervisor injects
into every add-on that declares ``homeassistant_api: true``. No long-lived
token, no .env to manage.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import SETTINGS

_LOGGER = logging.getLogger(__name__)


class SupervisorError(RuntimeError):
    pass


class SupervisorClient:
    def __init__(self) -> None:
        self._base = f"{SETTINGS.supervisor_url}/core/api"
        self._token = SETTINGS.supervisor_token

    @property
    def available(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        if not self._token:
            raise SupervisorError(
                "SUPERVISOR_TOKEN missing — Add-on muss mit homeassistant_api: true laufen"
            )
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def get_todo_items(self, entity_id: str) -> list[dict[str, Any]]:
        """Return all items of a todo list entity (open and completed)."""
        url = f"{self._base}/services/todo/get_items?return_response"
        payload = {"entity_id": entity_id}
        # Zeitüberschreitung und Verbindungsfehler sind ein gescheiterter
        # Abruf wie ein 500er; roh durchgereicht brachen sie den Abgleich
        # aller Konten ab und den manuellen Abgleich mit 500.
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise SupervisorError(f"todo.get_items failed for {entity_id}: {exc!r}") from exc
        if resp.status_code >= 400:
            raise SupervisorError(
                f"todo.get_items failed for {entity_id}: {resp.status_code} {resp.text}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise SupervisorError(f"todo.get_items for {entity_id}: keine JSON-Antwort") from exc
        # HA returns: {"service_response": {entity_id: {"items": [...]}}}
        svc_resp = (data.get("service_response") if isinstance(data, dict) else None) or {}
        bucket = svc_resp.get(entity_id) if isinstance(svc_resp, dict) else None
        if not isinstance(bucket, dict):
            # Fehlt die Liste in der Antwort (Entität gerade nicht geladen,
            # umbenannt), ist das kein „leer“: Der Abgleich würde sonst alle
            # offenen Aufgaben als in HA gelöscht wegräumen.
            raise SupervisorError(f"todo.get_items: {entity_id} fehlt in der Antwort")
        return bucket.get("items", []) or []

    async def update_todo_item(
        self,
        entity_id: str,
        item: str,
        *,
        status: str | None = None,
        rename: str | None = None,
    ) -> None:
        url = f"{self._base}/services/todo/update_item"
        payload: dict[str, Any] = {"entity_id": entity_id, "item": item}
        if status is not None:
            payload["status"] = status
        if rename is not None:
            payload["rename"] = rename
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise SupervisorError(f"todo.update_item failed for {entity_id}: {exc!r}") from exc
        if resp.status_code >= 400:
            raise SupervisorError(
                f"todo.update_item failed for {entity_id}: {resp.status_code} {resp.text}"
            )

    async def list_todo_entities(self) -> list[dict[str, Any]]:
        """All todo.* entities currently known to HA (for setup-screen pickers)."""
        return await self._states_with_prefix("todo.")

    async def list_calendar_entities(self) -> list[dict[str, Any]]:
        """All calendar.* entities (for the exam-calendar picker)."""
        return await self._states_with_prefix("calendar.")

    async def _states_with_prefix(self, prefix: str) -> list[dict[str, Any]]:
        url = f"{self._base}/states"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            raise SupervisorError(f"GET /states failed: {resp.status_code}")
        return [s for s in resp.json() if s.get("entity_id", "").startswith(prefix)]

    async def list_backups(self) -> dict[str, Any]:
        """Supervisor backups list (for 'last HA backup' status). This hits
        the Supervisor root API, not the Core proxy; it needs hassio_role
        backup, the default role answers 403."""
        url = f"{SETTINGS.supervisor_url}/backups"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            raise SupervisorError(f"GET /backups failed: {resp.status_code}")
        return resp.json().get("data", {}) or {}

    async def self_info(self) -> dict[str, Any]:
        """Slug and version of this add-on."""
        url = f"{SETTINGS.supervisor_url}/addons/self/info"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code >= 400:
            raise SupervisorError(f"GET /addons/self/info failed: {resp.status_code}")
        return resp.json().get("data", {}) or {}

    async def create_partial_backup(self, name: str, addons: list[str]) -> dict[str, Any]:
        """Ein Teil-Backup nur dieser Add-ons anlegen. Läuft im Supervisor
        synchron; bei 170 MB App-Datenbank dauert das eine Minute."""
        url = f"{SETTINGS.supervisor_url}/backups/new/partial"
        payload = {"name": name, "addons": addons, "compressed": True}
        async with httpx.AsyncClient(timeout=1800.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            raise SupervisorError(f"POST /backups/new/partial failed: {resp.status_code} {resp.text[:200]}")
        return resp.json().get("data", {}) or {}

    async def delete_backup(self, slug: str) -> None:
        url = f"{SETTINGS.supervisor_url}/backups/{slug}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.delete(url, headers=self._headers())
        if resp.status_code >= 400:
            raise SupervisorError(f"DELETE /backups/{slug} failed: {resp.status_code}")

    async def get_calendar_events(
        self, entity_id: str, start: str, end: str
    ) -> list[dict[str, Any]]:
        """Events of a calendar entity in [start, end] (ISO datetimes).

        Uses the Core REST endpoint GET /calendars/<entity>?start&end, which
        works for ICS subscription calendars (e.g. an iServ exam calendar).
        """
        # Familienkarte, Erledigen und Arbeiten fragen denselben Kalender oft
        # kurz hintereinander; eine Minute lang genügt die letzte Antwort.
        key = (entity_id, start, end)
        hit = _CALENDAR_CACHE.get(key)
        if hit and time.monotonic() - hit[0] < CALENDAR_CACHE_SECONDS:
            return [dict(e) for e in hit[1]]
        url = f"{self._base}/calendars/{entity_id}"
        params = {"start": start, "end": end}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
        if resp.status_code >= 400:
            raise SupervisorError(
                f"GET /calendars/{entity_id} failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        events = data if isinstance(data, list) else []
        if len(_CALENDAR_CACHE) > 64:
            _CALENDAR_CACHE.clear()
        _CALENDAR_CACHE[key] = (time.monotonic(), events)
        return [dict(e) for e in events]


CALENDAR_CACHE_SECONDS = 60
_CALENDAR_CACHE: dict[tuple[str, str, str], tuple[float, list]] = {}

_CLIENT: SupervisorClient | None = None


def get_supervisor() -> SupervisorClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = SupervisorClient()
    return _CLIENT
