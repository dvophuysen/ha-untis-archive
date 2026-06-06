"""Sensor entities for UNTIS Archive.

Per child:

- ``..._lehrstoff_heute``     – Lehrstoff der heutigen Stunden
- ``..._hausaufgaben_offen``  – Anzahl offener Hausaufgaben
- ``..._versaeumter_stoff``   – Lehrstoff der Stunden, in denen das Kind
                                laut WebUntis abwesend war (letzte 14 Tage)
- ``..._fehlzeiten_schuljahr`` – Anzahl Fehlzeiten-Einträge im laufenden
                                Schuljahr, plus Unentschuldigte als Attribut
- ``..._stundenplan_aenderungen`` – Anzahl Änderungen am Stundenplan
                                (Vertretungen, Raumwechsel, Ausfälle,
                                Lehrstoff-Updates, retroaktive Einträge)
                                in den letzten 7 Tagen
- ``..._fach_verlauf``        – Lehrstoff-Verlauf gruppiert pro Fach,
                                Quelle für die „Klassenarbeit lernen"-View
- ``..._krankheitsperioden``  – Krankheits-Perioden im Schuljahr mit
                                verpasstem Stoff pro Periode (gruppiert
                                nach Fach), Quelle für die Krankheits-
                                Ansicht im Dashboard
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
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


def _school_year_start(today: date) -> date:
    """German school year roughly starts in August. Anything before
    August belongs to the previous year's start.
    """
    year = today.year if today.month >= 8 else today.year - 1
    return date(year, 8, 1)


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
            FehlzeitenSchuljahrSensor(coordinator, entry, slug),
            StundenplanAenderungenSensor(coordinator, entry, slug),
            FachVerlaufSensor(coordinator, entry, slug),
            KrankheitsperiodenSensor(coordinator, entry, slug),
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
                    "teacher": r.get("teacher_name"),
                    "teacher_orig": r.get("teacher_orig_name"),
                    "room": r.get("room"),
                    "code": r.get("code") or "",
                    "was_absent": bool(r.get("was_absent")),
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
    """Lehrstoff der Stunden, in denen das Kind nach WebUntis abwesend war.

    Erkennung erfolgt automatisch über die ``was_absent``-Spalte, die der
    Coordinator aus den Fehlzeiten der Schule ableitet. Kein manueller
    Toggle nötig.
    """

    _attr_icon = "mdi:emoticon-sick"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_versaeumter_stoff"
        self._attr_translation_key = "versaeumter_stoff"
        self._attr_name = "Versäumter Stoff"

    def _window(self) -> tuple[str, str]:
        today = date.today()
        return (today - timedelta(days=14)).isoformat(), today.isoformat()

    def _missed(self) -> list[dict[str, Any]]:
        start, end = self._window()
        return self.coordinator.storage.missed_lessons(
            self.coordinator.account_id, start, end
        )

    @property
    def native_value(self) -> int:
        return len(self._missed())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = self._missed()
        return {
            "items": [
                {
                    "date": r.get("date"),
                    "start": r.get("start_time"),
                    "subject": r.get("subject_name"),
                    "teacher": r.get("teacher_name"),
                    "absence_reason": r.get("absence_reason"),
                    "lstext": r.get("lstext_manual_override") or r.get("lstext") or "",
                }
                for r in rows
            ]
        }


class FehlzeitenSchuljahrSensor(_Base):
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_fehlzeiten_schuljahr"
        self._attr_translation_key = "fehlzeiten_schuljahr"
        self._attr_name = "Fehlzeiten Schuljahr"

    def _absences(self) -> list[dict[str, Any]]:
        today = date.today()
        start = _school_year_start(today).isoformat()
        end = (today + timedelta(days=14)).isoformat()
        return self.coordinator.storage.absences_between(
            self.coordinator.account_id, start, end
        )

    @property
    def native_value(self) -> int:
        return len(self._absences())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = self._absences()
        unexcused = [r for r in rows if not r.get("is_excused")]
        return {
            "unexcused_count": len(unexcused),
            "items": [
                {
                    "start_date": r.get("start_date"),
                    "end_date": r.get("end_date"),
                    "start_time": r.get("start_time"),
                    "end_time": r.get("end_time"),
                    "reason": r.get("reason"),
                    "text": r.get("text"),
                    "is_excused": bool(r.get("is_excused")),
                }
                for r in rows[:50]
            ],
        }


class StundenplanAenderungenSensor(_Base):
    """Zählt alle Stundenplan-Änderungen der letzten 7 Tage.

    Greift auf das ``lesson_snapshots``-Change-Log zu — also alle
    Vertretungen, Raumwechsel, Ausfälle, Lehrstoff-Updates und
    retroaktive Einträge die der Coordinator beobachtet hat.
    """

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_stundenplan_aenderungen"
        self._attr_translation_key = "stundenplan_aenderungen"
        self._attr_name = "Stundenplan-Änderungen (7 Tage)"

    def _changes(self) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
        return self.coordinator.storage.recent_lesson_changes(
            self.coordinator.account_id, since
        )

    @property
    def native_value(self) -> int:
        return len(self._changes())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = self._changes()
        items = []
        for r in rows[:50]:
            try:
                types = json.loads(r.get("change_types_json") or "[]")
            except ValueError:
                types = []
            items.append(
                {
                    "captured_at": r.get("captured_at"),
                    "date": r.get("date"),
                    "start": r.get("start_time"),
                    "subject": r.get("subject_name"),
                    "teacher": r.get("teacher_name"),
                    "teacher_orig": r.get("teacher_orig_name"),
                    "room": r.get("room"),
                    "room_orig": r.get("room_orig"),
                    "code": r.get("code") or "",
                    "change_types": types,
                }
            )
        return {"items": items}


class FachVerlaufSensor(_Base):
    """Lehrstoff-Verlauf gruppiert pro Fach im laufenden Schuljahr.

    Liefert in ``subjects`` ein Dict ``{Fachname: [Stunden …]}``,
    neueste Stunde zuerst, ausgefallene Stunden ausgeblendet. ``state``
    ist die Anzahl Fächer mit mindestens einem dokumentierten Eintrag.
    Quelle für die „Klassenarbeit lernen"-Dashboardseite.
    """

    _attr_icon = "mdi:bookshelf"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_fach_verlauf"
        self._attr_translation_key = "fach_verlauf"
        self._attr_name = "Fach-Verlauf"

    def _rows(self) -> list[dict[str, Any]]:
        today = date.today()
        start = _school_year_start(today).isoformat()
        end = today.isoformat()
        return self.coordinator.storage.lessons_between(
            self.coordinator.account_id, start, end
        )

    @property
    def native_value(self) -> int:
        rows = self._rows()
        subjects: set[str] = set()
        for r in rows:
            if (r.get("code") or "") == "cancelled":
                continue
            name = r.get("subject_name")
            if name:
                subjects.add(name)
        return len(subjects)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = self._rows()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            if (r.get("code") or "") == "cancelled":
                continue
            name = r.get("subject_name")
            if not name:
                continue
            topic = r.get("lstext_manual_override") or r.get("lstext") or ""
            grouped.setdefault(name, []).append(
                {
                    "date": r.get("date"),
                    "start": r.get("start_time"),
                    "code": r.get("code") or "",
                    "was_absent": bool(r.get("was_absent")),
                    "teacher": r.get("teacher_name"),
                    "room": r.get("room"),
                    "topic": topic,
                }
            )
        # Neueste zuerst, pro Fach. Listen kappen, damit das Sensor-
        # Attribut nicht ins Uferlose wächst (recorder speichert das
        # bei jedem state-change).
        subjects_capped: dict[str, list[dict[str, Any]]] = {}
        for name, items in grouped.items():
            items.sort(key=lambda x: (x["date"] or "", x["start"] or 0), reverse=True)
            subjects_capped[name] = items[:80]
        return {
            "subject_list": sorted(subjects_capped.keys()),
            "subjects": subjects_capped,
        }


class KrankheitsperiodenSensor(_Base):
    """Krankheits-Perioden im Schuljahr mit verpasstem Stoff pro Periode.

    Jede Absence aus Untis bildet eine Periode (start_date – end_date).
    Pro Periode werden die ``was_absent=1``-Stunden in dem Zeitraum
    gesammelt und nach Fach gruppiert, damit man im Dashboard sofort
    sieht „in der Krankheit vom 03.–07.06. habe ich in Mathe x, y, z
    verpasst".
    """

    _attr_icon = "mdi:bed"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_krankheitsperioden"
        self._attr_translation_key = "krankheitsperioden"
        self._attr_name = "Krankheitsperioden"

    def _build(self) -> list[dict[str, Any]]:
        today = date.today()
        start = _school_year_start(today).isoformat()
        end = (today + timedelta(days=14)).isoformat()
        absences = self.coordinator.storage.absences_between(
            self.coordinator.account_id, start, end
        )
        periods: list[dict[str, Any]] = []
        for ab in absences:
            ab_start = ab.get("start_date") or ""
            ab_end = ab.get("end_date") or ab_start
            if not ab_start:
                continue
            missed = self.coordinator.storage.missed_lessons(
                self.coordinator.account_id, ab_start, ab_end
            )
            # Auf das tatsächliche Krankheitsfenster zuschneiden — die
            # storage-Abfrage liefert alle was_absent=1-Stunden im Datums-
            # Bereich, was bei mehreren Absences am selben Tag genügt.
            by_subject: dict[str, list[dict[str, Any]]] = {}
            for r in missed:
                name = r.get("subject_name") or "—"
                topic = r.get("lstext_manual_override") or r.get("lstext") or ""
                by_subject.setdefault(name, []).append(
                    {
                        "date": r.get("date"),
                        "start": r.get("start_time"),
                        "code": r.get("code") or "",
                        "teacher": r.get("teacher_name"),
                        "room": r.get("room"),
                        "topic": topic,
                    }
                )
            for items in by_subject.values():
                items.sort(key=lambda x: (x["date"] or "", x["start"] or 0))
            periods.append(
                {
                    "start_date": ab_start,
                    "end_date": ab_end,
                    "reason": ab.get("reason") or ab.get("text") or "",
                    "is_excused": bool(ab.get("is_excused")),
                    "lessons_count": sum(len(v) for v in by_subject.values()),
                    "subjects": by_subject,
                }
            )
        periods.sort(key=lambda p: p["start_date"], reverse=True)
        return periods

    @property
    def native_value(self) -> int:
        return len(self._build())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"periods": self._build()}
