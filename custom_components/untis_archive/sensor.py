"""Sensor entities for UNTIS Archive.

Three sensors per child:

- ``..._lehrstoff_heute``   – Lehrstoff der heutigen Stunden
- ``..._hausaufgaben_offen`` – Anzahl offener Hausaufgaben
- ``..._versaeumter_stoff``  – Lehrstoff verpasster Tage (greift
  ``input_boolean.kind_<slug>_krank`` ab, falls vorhanden)
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UntisCoordinator


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "kind"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UntisCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    slug = _slug(entry.title)
    async_add_entities(
        [
            LehrstoffHeuteSensor(coordinator, entry, slug),
            HausaufgabenOffenSensor(coordinator, entry, slug),
            VersaeumterStoffSensor(coordinator, entry, slug),
        ]
    )


class _Base(CoordinatorEntity[UntisCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._slug = slug
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"UNTIS Archive – {entry.title}",
            "manufacturer": "WebUntis",
            "model": "Untis Archive",
        }


class LehrstoffHeuteSensor(_Base):
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_lehrstoff_heute"
        self._attr_translation_key = "lehrstoff_heute"
        self._attr_name = "Lehrstoff heute"

    def _read(self) -> list[dict[str, Any]]:
        today = date.today().isoformat()
        return self.coordinator.storage.lessons_for_day(self.coordinator.account_id, today)

    @property
    def native_value(self) -> int:
        rows = self._read()
        return sum(1 for r in rows if (r.get("lstext") or r.get("lstext_manual_override")))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = self._read()
        items = []
        for r in rows:
            text = r.get("lstext_manual_override") or r.get("lstext") or ""
            items.append(
                {
                    "subject": r.get("subject_name"),
                    "start": r.get("start_time"),
                    "code": r.get("code") or "",
                    "lstext": text,
                }
            )
        return {"items": items}


class HausaufgabenOffenSensor(_Base):
    _attr_icon = "mdi:notebook-edit"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_hausaufgaben_offen"
        self._attr_translation_key = "hausaufgaben_offen"
        self._attr_name = "Hausaufgaben offen"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.storage.open_homework(self.coordinator.account_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.storage.open_homework(self.coordinator.account_id)
        return {
            "items": [
                {
                    "subject": h.get("subject_name"),
                    "text": h.get("text"),
                    "due_date": h.get("due_date"),
                    "assigned_date": h.get("assigned_date"),
                }
                for h in items
            ]
        }


class VersaeumterStoffSensor(_Base):
    """Lehrstoff von Tagen, an denen das Kind krank war.

    Erkennung: ``input_boolean.kind_<slug>_krank`` ist (oder war heute)
    aktiv. Vereinfachte Variante: zeigt den Lehrstoff der letzten 7 Tage
    der entsprechenden Stunden.
    """

    _attr_icon = "mdi:emoticon-sick"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_versaeumter_stoff"
        self._attr_translation_key = "versaeumter_stoff"
        self._attr_name = "Versäumter Stoff"

    def _is_sick(self) -> bool:
        state = self.hass.states.get(f"input_boolean.kind_{self._slug}_krank")
        return bool(state and state.state == "on")

    @property
    def native_value(self) -> int:
        if not self._is_sick():
            return 0
        today = date.today()
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
        rows = self.coordinator.storage.lessons_between(
            self.coordinator.account_id, start, end
        )
        return sum(1 for r in rows if (r.get("lstext") or r.get("lstext_manual_override")))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self._is_sick():
            return {"hint": "Aktiviere input_boolean.kind_<name>_krank, um den verpassten Stoff zu sehen."}
        today = date.today()
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
        rows = self.coordinator.storage.lessons_between(
            self.coordinator.account_id, start, end
        )
        return {
            "items": [
                {
                    "date": r.get("date"),
                    "subject": r.get("subject_name"),
                    "lstext": r.get("lstext_manual_override") or r.get("lstext"),
                }
                for r in rows
                if (r.get("lstext") or r.get("lstext_manual_override"))
            ]
        }
