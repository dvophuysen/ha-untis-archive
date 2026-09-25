"""Backup-Plattform: ``history.db`` konsistent in die HA-Sicherung bringen.

Die Datenbank läuft im WAL-Modus. Kopiert die Sicherung ``history.db``
während eines Checkpoints, landet eine halb geschriebene Datei im Archiv.
Vor der Sicherung schreibt ``async_pre_backup`` das WAL deshalb in die
Datenbank und schaltet die automatischen Checkpoints ab; danach ändert
sich ``history.db`` bis ``async_post_backup`` nicht mehr, neue Schreibvorgänge
gehen nur ins ``-wal``.

Beide Funktionen werfen nie: Ein Fehler hier würde die ganze HA-Sicherung
abbrechen. Kommt ``async_post_backup`` nicht (Sicherung abgestürzt), schaltet
ein Zeitgeber die Checkpoints nach einigen Stunden wieder ein; bis dahin
wächst nur das ``-wal``.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_RESTORE_AFTER = timedelta(hours=6)
_TIMER_KEY = f"{DOMAIN}_backup_timer"


def _storages(hass: HomeAssistant) -> list[Any]:
    out = []
    for bucket in (hass.data.get(DOMAIN) or {}).values():
        coordinator = bucket.get("coordinator") if isinstance(bucket, dict) else None
        storage = getattr(coordinator, "_storage", None)
        if storage is not None:
            out.append(storage)
    return out


async def _finish(hass: HomeAssistant) -> None:
    for storage in _storages(hass):
        try:
            await hass.async_add_executor_job(storage.finish_backup)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Checkpoints nach der Sicherung nicht wieder an", exc_info=True)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Vor der Sicherung: WAL leeren, Checkpoints aus."""
    for storage in _storages(hass):
        try:
            busy, _log, _done = await hass.async_add_executor_job(storage.prepare_backup)
            if busy:
                _LOGGER.info("history.db: Checkpoint vor der Sicherung nicht vollständig")
        except Exception:  # noqa: BLE001
            _LOGGER.warning("history.db vor der Sicherung nicht vorbereitet", exc_info=True)

    @callback
    def _timeout(_now: Any) -> None:
        hass.data.pop(_TIMER_KEY, None)
        hass.async_create_task(_finish(hass))

    old = hass.data.pop(_TIMER_KEY, None)
    if old is not None:
        old()
    hass.data[_TIMER_KEY] = async_call_later(hass, _RESTORE_AFTER, _timeout)


async def async_post_backup(hass: HomeAssistant) -> None:
    """Nach der Sicherung: Checkpoints wieder an."""
    unsub = hass.data.pop(_TIMER_KEY, None)
    if unsub is not None:
        unsub()
    await _finish(hass)
