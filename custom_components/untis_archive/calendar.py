"""Calendar entity exposing UNTIS lessons (with Lehrstoff in the body)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import UntisCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UntisCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([UntisCalendar(coordinator, entry)])


def _hhmm_to_time(value: int) -> time:
    h, m = divmod(int(value), 100)
    return time(hour=h, minute=m)


def _event_from_row(row: dict[str, Any]) -> CalendarEvent:
    day = date.fromisoformat(row["date"])
    start_local = datetime.combine(day, _hhmm_to_time(row["start_time"]))
    end_local = datetime.combine(day, _hhmm_to_time(row["end_time"]))
    tz = dt_util.get_default_time_zone()
    start = start_local.replace(tzinfo=tz)
    end = end_local.replace(tzinfo=tz)

    subject = row.get("subject_name") or "Unterricht"
    code = row.get("code") or ""
    summary = subject
    if code == "cancelled":
        summary = f"❌ {subject} (Entfall)"
    elif code == "irregular":
        summary = f"↺ {subject} (Vertretung)"

    parts: list[str] = []
    lstext = row.get("lstext_manual_override") or row.get("lstext") or ""
    if lstext:
        parts.append(f"Lehrstoff: {lstext}")
    if row.get("subst_text"):
        parts.append(f"Hinweis: {row['subst_text']}")
    if row.get("info"):
        parts.append(f"Info: {row['info']}")
    if row.get("teacher_name"):
        parts.append(f"Lehrer: {row['teacher_name']}")

    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description="\n".join(parts) or None,
        location=row.get("room") or None,
    )


class UntisCalendar(CoordinatorEntity[UntisCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Stundenplan"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"UNTIS Archive – {entry.title}",
            "manufacturer": "WebUntis",
            "model": "Untis Archive",
        }

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        today_rows = self.coordinator.storage.lessons_for_day(
            self.coordinator.account_id, now.date().isoformat()
        )
        upcoming: CalendarEvent | None = None
        for row in today_rows:
            ev = _event_from_row(row)
            if ev.end >= now and (upcoming is None or ev.start < upcoming.start):
                upcoming = ev
        return upcoming

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start_day = start_date.date().isoformat()
        end_day = end_date.date().isoformat()
        rows = await hass.async_add_executor_job(
            self.coordinator.storage.lessons_between,
            self.coordinator.account_id,
            start_day,
            end_day,
        )
        events: list[CalendarEvent] = []
        for row in rows:
            try:
                events.append(_event_from_row(row))
            except (KeyError, ValueError):
                continue
        return events
