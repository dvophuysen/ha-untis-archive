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
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, OPEN_HOMEWORK_MAX_OVERDUE_DAYS
from .coordinator import UntisCoordinator

_LOGGER = logging.getLogger(__name__)

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
    """Gemeinsamer Unterbau: Wert und Attribute werden einmal je Aktualisierung
    im Executor aus der Datenbank gelesen und zwischengespeichert.

    Bis 0.5.3 lasen ``native_value`` und ``extra_state_attributes`` die
    SQLite-Datenbank direkt, in der Ereignisschleife von Home Assistant und
    bei jedem Schreiben des Zustands zweimal.
    """

    _attr_has_entity_name = True
    # Die Listen stehen für Dashboards im Zustand, gehören aber nicht in die
    # Verlaufsdatenbank: Der Fach-Verlauf ist größer als 16 KB, der Recorder
    # warnte bei jeder Aktualisierung und speicherte ihn trotzdem nicht.
    _unrecorded_attributes = frozenset({"items", "subjects", "subject_list", "periods"})

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._slug = slug
        self._value: int | None = None
        self._attrs: dict[str, Any] = {}
        self._db_ok = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"UNTIS Archive – {entry.title}",
            "manufacturer": "WebUntis",
            "model": "Untis Archive",
        }

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        """Wert und Attribute aus der Datenbank; läuft im Executor.

        ``today`` ist das Datum in der Zeitzone von HA, bestimmt in der
        Ereignisschleife."""
        raise NotImplementedError

    async def _async_recompute(self, write: bool = True) -> None:
        today = dt_util.now().date()
        try:
            self._value, self._attrs = await self.hass.async_add_executor_job(
                self._compute, today
            )
            self._db_ok = True
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Sensor %s: Datenbank nicht lesbar", self.entity_id)
            self._db_ok = False
        if write:
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        # Die Werte kommen aus der lokalen Datenbank. Ein fehlgeschlagener
        # WebUntis-Abruf (Wartung, Netz) macht sie nicht falsch; bis 0.5.4
        # wurden alle Sensoren dann „nicht verfügbar“.
        return self.coordinator.storage_ready and self._db_ok

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Den ersten Zustand schreibt die Plattform selbst nach dieser Methode.
        await self._async_recompute(write=False)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._async_recompute())

    @property
    def native_value(self) -> int | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attrs


class LehrstoffHeuteSensor(_Base):
    _attr_icon = "mdi:book-open-page-variant"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_lehrstoff_heute"
        self._attr_translation_key = "lehrstoff_heute"
        self._attr_name = "Lehrstoff heute"

    def _read(self, today: date) -> list[dict[str, Any]]:
        return self.coordinator.storage.lessons_for_day(
            self.coordinator.account_id, today.isoformat()
        )

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        rows = self._read(today)
        value = sum(1 for r in rows if (r.get("lstext") or r.get("lstext_manual_override")))
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
        return value, {"items": items}


class HausaufgabenOffenSensor(_Base):
    _attr_icon = "mdi:notebook-edit"

    def __init__(self, coordinator: UntisCoordinator, entry: ConfigEntry, slug: str) -> None:
        super().__init__(coordinator, entry, slug)
        self._attr_unique_id = f"{entry.entry_id}_hausaufgaben_offen"
        self._attr_translation_key = "hausaufgaben_offen"
        self._attr_name = "Hausaufgaben offen"

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        # Länger als zwei Wochen überfällige, nie abgehakte Aufgaben fallen
        # heraus; ohne Grenze wuchs die Liste unbegrenzt.
        items = self.coordinator.storage.open_homework(
            self.coordinator.account_id,
            (today - timedelta(days=OPEN_HOMEWORK_MAX_OVERDUE_DAYS)).isoformat(),
        )
        return len(items), {
            "items": [
                {
                    # Echte WebUntis-Hausaufgaben-ID — der einzige wirklich
                    # eindeutige Schlüssel. Automationen sollten diese ID
                    # in die ToDo-Description übernehmen (z.B. als Tag
                    # "[MA12345]"), denn Fach + Datum allein kollidiert,
                    # sobald am selben Tag zwei Aufgaben im selben Fach
                    # aufgegeben werden.
                    "id": h.get("untis_homework_id"),
                    "subject": h.get("subject_name"),
                    # Untis-Kürzel (z.B. "MA") aus dem Stundenplan — als
                    # Tag-Präfix für Automationen ("[MA12345]").
                    "subject_code": h.get("subject_code"),
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

    def _window(self, today: date) -> tuple[str, str]:
        return (today - timedelta(days=14)).isoformat(), today.isoformat()

    def _missed(self, today: date) -> list[dict[str, Any]]:
        start, end = self._window(today)
        return self.coordinator.storage.missed_lessons(
            self.coordinator.account_id, start, end
        )

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        rows = self._missed(today)
        return len(rows), {
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

    def _absences(self, today: date) -> list[dict[str, Any]]:
        start = _school_year_start(today).isoformat()
        end = (today + timedelta(days=14)).isoformat()
        return self.coordinator.storage.absences_between(
            self.coordinator.account_id, start, end
        )

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        rows = self._absences(today)
        unexcused = [r for r in rows if not r.get("is_excused")]
        return len(rows), {
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

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
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
        return len(rows), {"items": items}


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

    def _rows(self, today: date) -> list[dict[str, Any]]:
        start = _school_year_start(today).isoformat()
        end = today.isoformat()
        return self.coordinator.storage.lessons_between(
            self.coordinator.account_id, start, end
        )

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        rows = self._rows(today)
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
        # Zustand: Anzahl Fächer mit mindestens einer nicht ausgefallenen Stunde.
        return len(subjects_capped), {
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

    def _build(self, today: date) -> list[dict[str, Any]]:
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

    def _compute(self, today: date) -> tuple[int, dict[str, Any]]:
        periods = self._build(today)
        return len(periods), {"periods": periods}
