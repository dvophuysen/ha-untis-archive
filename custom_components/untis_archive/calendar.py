"""Calendar entities exposing UNTIS data.

Zwei Kalender pro Kind:

- ``calendar.*_stundenplan`` — jede Stunde als Termin, Lehrstoff im
  Description-Feld, Status-Präfix (❌ Entfall, ↺ Vertretung, 🤒 versäumt)
  im Titel.
- ``calendar.*_ereignisse`` — Krankheits-Perioden (ganztägig) und
  Klassenarbeiten / Klausuren (aus ``lessons.period_info_json.exam``).
"""

from __future__ import annotations

import json
import logging
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UntisCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            UntisCalendar(coordinator, entry),
            UntisEreignisseCalendar(coordinator, entry),
        ]
    )


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
    was_absent = bool(row.get("was_absent"))
    if code == "cancelled":
        summary = f"❌ {subject} (Entfall)"
    elif was_absent:
        summary = f"🤒 {subject} (versäumt)"
    elif code == "irregular":
        summary = f"↺ {subject} (Vertretung)"
    else:
        summary = subject

    parts: list[str] = []
    lstext = row.get("lstext_manual_override") or row.get("lstext") or ""
    if lstext:
        parts.append(f"Lehrstoff: {lstext}")
    if row.get("subst_text"):
        parts.append(f"Hinweis: {row['subst_text']}")
    if row.get("info"):
        parts.append(f"Info: {row['info']}")
    teacher = row.get("teacher_name")
    teacher_orig = row.get("teacher_orig_name")
    if teacher and teacher_orig and teacher_orig != teacher:
        parts.append(f"Lehrer: {teacher} (statt {teacher_orig})")
    elif teacher:
        parts.append(f"Lehrer: {teacher}")
    room = row.get("room")
    room_orig = row.get("room_orig")
    if room and room_orig and room_orig != room:
        parts.append(f"Raum: {room} (statt {room_orig})")
    if row.get("absence_reason"):
        parts.append(f"Fehlgrund: {row['absence_reason']}")

    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description="\n".join(parts) or None,
        location=row.get("room") or None,
    )


def _exam_from_row(row: dict[str, Any]) -> CalendarEvent | None:
    """Klassenarbeit/Klausur aus ``period_info_json`` extrahieren.

    Die Untis-Antwort variiert je nach Schule. Wir suchen defensiv nach
    einem ``exam``-Objekt (oder einer Liste davon) und fallen still
    zurück wenn das Feld leer ist oder die Schule diesen Schlüssel
    nicht ausliefert.
    """
    raw = row.get("period_info_json")
    if not raw:
        return None
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return None

    exam = _find_exam(payload)
    if not exam:
        return None

    try:
        day = date.fromisoformat(row["date"])
        start_local = datetime.combine(day, _hhmm_to_time(row["start_time"]))
        end_local = datetime.combine(day, _hhmm_to_time(row["end_time"]))
    except (KeyError, ValueError):
        return None
    tz = dt_util.get_default_time_zone()
    start = start_local.replace(tzinfo=tz)
    end = end_local.replace(tzinfo=tz)

    subject = row.get("subject_name") or "Unterricht"
    name = (
        exam.get("name")
        or exam.get("text")
        or exam.get("examType")
        or "Klassenarbeit"
    )
    summary = f"📝 {subject}: {name}"
    desc_parts: list[str] = [f"Fach: {subject}"]
    if exam.get("text") and exam.get("text") != name:
        desc_parts.append(f"Hinweis: {exam['text']}")
    if exam.get("examType"):
        desc_parts.append(f"Typ: {exam['examType']}")
    if row.get("teacher_name"):
        desc_parts.append(f"Lehrer: {row['teacher_name']}")
    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description="\n".join(desc_parts),
        location=row.get("room") or None,
    )


def _find_exam(payload: Any) -> dict[str, Any] | None:
    """Walk the period-info payload looking for the first ``exam`` dict."""
    if isinstance(payload, dict):
        exam = payload.get("exam")
        if isinstance(exam, dict) and exam:
            return exam
        if isinstance(exam, list) and exam:
            for entry in exam:
                if isinstance(entry, dict):
                    return entry
        for value in payload.values():
            found = _find_exam(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_exam(item)
            if found:
                return found
    return None


def _absence_event(row: dict[str, Any]) -> CalendarEvent | None:
    start_iso = row.get("start_date")
    end_iso = row.get("end_date") or start_iso
    if not start_iso:
        return None
    try:
        start_day = date.fromisoformat(start_iso)
        end_day = date.fromisoformat(end_iso)
    except ValueError:
        return None
    # Calendar all-day events use end-exclusive semantics.
    end_excl = end_day + timedelta(days=1)
    reason = row.get("reason") or row.get("text") or "Fehlzeit"
    excused = "✅ entschuldigt" if row.get("is_excused") else "⚠️ unentschuldigt"
    summary = f"🤒 {reason}"
    desc_parts = [excused]
    if row.get("text") and row.get("text") != reason:
        desc_parts.append(row["text"])
    if not (row.get("start_time") in (0, None) and row.get("end_time") in (0, None)):
        desc_parts.append(
            f"Zeitraum: {row.get('start_time'):04d}–{row.get('end_time'):04d}"
        )
    return CalendarEvent(
        start=start_day,
        end=end_excl,
        summary=summary,
        description="\n".join(desc_parts),
    )


class _BaseCalendar(CoordinatorEntity[UntisCoordinator], CalendarEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"UNTIS Archive – {entry.title}",
            "manufacturer": "WebUntis",
            "model": "Untis Archive",
        }


class UntisCalendar(_BaseCalendar):
    _attr_name = "Stundenplan"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_calendar"

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


class UntisEreignisseCalendar(_BaseCalendar):
    """Zweiter Kalender: Fehltage und Klassenarbeiten.

    Wird im Dashboard zusammen mit dem Stundenplan-Kalender in einer
    Monatsansicht (atomic-calendar-revive) angezeigt — Fehltage als
    ganztägige Markierung, Klassenarbeiten als zeit-gebundenes Event.
    """

    _attr_name = "Ereignisse"
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_calendar_ereignisse"

    @property
    def event(self) -> CalendarEvent | None:
        # Nächstes anstehendes Ereignis (Klassenarbeit oder Fehlzeit-Beginn).
        now = dt_util.now()
        window_end = now + timedelta(days=30)
        try:
            events = self._build_events(now.date(), window_end.date())
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Ereignis-Kalender (event) fehlgeschlagen")
            return None
        upcoming: CalendarEvent | None = None
        for ev in events:
            ev_start = (
                ev.start
                if isinstance(ev.start, datetime)
                else datetime.combine(ev.start, time(0, 0), tzinfo=dt_util.get_default_time_zone())
            )
            if ev_start >= now and (upcoming is None or ev_start < (
                upcoming.start if isinstance(upcoming.start, datetime)
                else datetime.combine(upcoming.start, time(0, 0), tzinfo=dt_util.get_default_time_zone())
            )):
                upcoming = ev
        return upcoming

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return await hass.async_add_executor_job(
            self._build_events, start_date.date(), end_date.date()
        )

    def _build_events(self, start_day: date, end_day: date) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        # Fehlzeiten als Ganztages-Events.
        absences = self.coordinator.storage.absences_between(
            self.coordinator.account_id, start_day.isoformat(), end_day.isoformat()
        )
        for row in absences:
            ev = _absence_event(row)
            if ev is not None:
                events.append(ev)
        # Klassenarbeiten aus period_info_json der Lessons im Bereich.
        lessons = self.coordinator.storage.lessons_between(
            self.coordinator.account_id, start_day.isoformat(), end_day.isoformat()
        )
        for row in lessons:
            ev = _exam_from_row(row)
            if ev is not None:
                events.append(ev)
        return events
