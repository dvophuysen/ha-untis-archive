"""Thin wrapper around the HA Supervisor's proxy to the Core REST API.

Auth is via the SUPERVISOR_TOKEN env var, which the Supervisor injects
into every add-on that declares ``homeassistant_api: true``. No long-lived
token, no .env to manage.
"""

from __future__ import annotations

import logging
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            raise SupervisorError(
                f"todo.get_items failed for {entity_id}: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        # HA returns: {"service_response": {entity_id: {"items": [...]}}}
        svc_resp = data.get("service_response", {}) or {}
        bucket = svc_resp.get(entity_id, {}) or {}
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
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

    async def get_calendar_events(
        self, entity_id: str, start: str, end: str
    ) -> list[dict[str, Any]]:
        """Events of a calendar entity in [start, end] (ISO datetimes).

        Uses the Core REST endpoint GET /calendars/<entity>?start&end, which
        works for ICS subscription calendars (e.g. an iServ exam calendar).
        """
        url = f"{self._base}/calendars/{entity_id}"
        params = {"start": start, "end": end}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
        if resp.status_code >= 400:
            raise SupervisorError(
                f"GET /calendars/{entity_id} failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return data if isinstance(data, list) else []


_CLIENT: SupervisorClient | None = None


def get_supervisor() -> SupervisorClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = SupervisorClient()
    return _CLIENT
