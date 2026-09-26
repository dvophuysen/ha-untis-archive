"""DataUpdateCoordinator that pulls WebUntis and persists into SQLite."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import UntisApiError, UntisAuthError, UntisClient
from .const import (
    ABSENCE_MAX_DELETIONS_PER_PULL,
    ABSENCE_WINDOW_DAYS_BACK,
    ABSENCE_WINDOW_DAYS_FORWARD,
    CONF_PASSWORD,
    CONF_SCHOOL,
    CONF_SERVER,
    CONF_STUDENT_ID,
    CONF_USERNAME,
    DB_FILENAME,
    DB_SUBDIR,
    DOMAIN,
    HOMEWORK_WINDOW_DAYS_BACK,
    HOMEWORK_WINDOW_DAYS_FORWARD,
    INVALID_CREDENTIALS,
    STUDENT_ELEMENT_TYPE,
    TOPIC_BACKFILL_DAYS,
    TOPIC_BACKFILL_MAX_PER_PULL,
    UPDATE_INTERVAL_HOURS,
    WINDOW_DAYS_BACK,
    WINDOW_DAYS_FORWARD,
)
from .storage import (
    UntisStorage,
    absence_ids_in_payload,
    collect_absences,
    collect_homework,
    normalize_period,
    to_iso_date,
)

_LOGGER = logging.getLogger(__name__)


def _count(results: list[Any], *actions: str) -> list[int]:
    """Anzahl je Ergebnis (``"inserted"`` usw.) in einer Batch-Antwort."""
    names = [getattr(r, "action", r) for r in results]
    return [sum(1 for n in names if n == a) for a in actions]


class UntisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the timetable ±14 days every hour and stores everything."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # Ausdrücklich statt über den ContextVar, den HA abkündigt.
            config_entry=entry,
            name=f"{DOMAIN}:{entry.title}",
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )
        self._entry = entry
        self._db_path = Path(hass.config.path(DB_SUBDIR, DB_FILENAME))
        self._storage: UntisStorage | None = None
        self._account_id: int | None = None

    @property
    def storage(self) -> UntisStorage:
        if self._storage is None:
            raise RuntimeError("storage not initialised yet")
        return self._storage

    @property
    def storage_ready(self) -> bool:
        """Datenbank offen und Konto angelegt: Die Entitäten können lesen,
        auch wenn der letzte WebUntis-Abruf fehlschlug."""
        return self._storage is not None and self._account_id is not None

    @property
    def account_id(self) -> int:
        if self._account_id is None:
            raise RuntimeError("account not registered yet")
        return self._account_id

    async def async_setup(self) -> None:
        """Open the database and register the account row."""
        self._storage = await self.hass.async_add_executor_job(UntisStorage, self._db_path)
        data = self._entry.data
        student_id = data.get(CONF_STUDENT_ID)
        self._account_id = await self.hass.async_add_executor_job(
            lambda: self.storage.ensure_account(
                entry_id=self._entry.entry_id,
                name=self._entry.title,
                server=data[CONF_SERVER],
                school=data[CONF_SCHOOL],
                username=data[CONF_USERNAME],
                student_id=student_id,
                student_type=None,
            )
        )

    async def async_shutdown(self) -> None:
        # Geplante Abrufe und den Debouncer der Basisklasse beenden, bevor
        # die Verbindung zugeht; sonst lief ein Abruf gegen eine
        # geschlossene Datenbank.
        await super().async_shutdown()
        storage, self._storage = self._storage, None
        if storage is not None:
            await self.hass.async_add_executor_job(storage.close)

    async def _async_update_data(self) -> dict[str, Any]:
        data = self._entry.data
        # Datum in der Zeitzone von HA, nicht der des Containers (UTC):
        # sonst lag „heute“ zwischen 0 und 2 Uhr noch auf gestern.
        today = dt_util.now().date()
        today_iso = today.isoformat()
        start = today - timedelta(days=WINDOW_DAYS_BACK)
        end = today + timedelta(days=WINDOW_DAYS_FORWARD)
        absence_start = today - timedelta(days=ABSENCE_WINDOW_DAYS_BACK)
        absence_end = today + timedelta(days=ABSENCE_WINDOW_DAYS_FORWARD)
        homework_start = today - timedelta(days=HOMEWORK_WINDOW_DAYS_BACK)
        homework_end = today + timedelta(days=HOMEWORK_WINDOW_DAYS_FORWARD)
        storage = self.storage
        account_id = self.account_id

        client = UntisClient(
            data[CONF_SERVER],
            data[CONF_SCHOOL],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        try:
            try:
                session = await client.login()
            except UntisAuthError as err:
                # Nur ein abgelehntes Passwort löst die Neuanmeldung in HA aus;
                # eine vorübergehende Sperre (zu viele Versuche) oder ein
                # Netzfehler nicht.
                if err.code == INVALID_CREDENTIALS:
                    raise ConfigEntryAuthFailed(
                        f"WebUntis lehnt die Zugangsdaten ab: {err}"
                    ) from err
                raise UpdateFailed(f"WebUntis-Login fehlgeschlagen: {err}") from err

            # Mit gesetzter Schüler-ID gilt sie für Stundenplan, Lehrstoff und
            # Fehlzeiten, als Element vom Typ Schüler. Bis 0.5.4 blieb der Typ
            # der des angemeldeten Kontos und die Fehlzeiten kamen immer für
            # das angemeldete Konto.
            student_override = data.get(CONF_STUDENT_ID)
            if student_override:
                elem_id = int(student_override)
                elem_type = STUDENT_ELEMENT_TYPE
            else:
                elem_id = session.person_id
                elem_type = session.person_type

            # Polling optimisation: skip the (expensive) timetable +
            # period/info pass when the server reports the same import
            # timestamp as on our previous pull. Homework and absences
            # come from independent endpoints and are still refreshed.
            try:
                latest_import = await client.get_latest_import_time()
            except UntisApiError as err:
                _LOGGER.debug("getLatestImportTime failed: %s", err)
                latest_import = None
            previous_import = await self.hass.async_add_executor_job(
                storage.get_latest_import_time, account_id
            )
            timetable_dirty = (
                latest_import is None
                or previous_import is None
                or latest_import != previous_import
            )

            raw_timetable: list[dict[str, Any]] = []
            if timetable_dirty:
                try:
                    raw_timetable = await client.get_timetable(
                        start, end, elem_id=elem_id, elem_type=elem_type
                    )
                except UntisApiError as err:
                    raise UpdateFailed(f"Stundenplan-Abruf fehlgeschlagen: {err}") from err
            else:
                _LOGGER.debug(
                    "Stundenplan unverändert (import_time=%s), Pass übersprungen",
                    latest_import,
                )

            lessons: list[dict[str, Any]] = []
            returned_ids: set[int] = set()
            ids_complete = True
            for raw in raw_timetable:
                try:
                    returned_ids.add(int(raw["id"]))
                except (KeyError, TypeError, ValueError):
                    ids_complete = False
                try:
                    lessons.append(normalize_period(raw))
                except (KeyError, TypeError, ValueError, AttributeError) as err:
                    _LOGGER.debug("Skip malformed period %r: %s", raw, err)
            results = await self.hass.async_add_executor_job(
                partial(storage.upsert_lessons, account_id, lessons, today=today_iso)
            )
            inserted, updated, unchanged = _count(results, "inserted", "updated", "unchanged")

            # Geisterstunden: nur für Tage, an denen WebUntis in diesem Abruf
            # mindestens eine Stunde geliefert hat, und nur, wenn jede
            # gelieferte Stunde eine lesbare ID hatte.
            removed = restored = 0
            covered_days = {
                lesson["date"]
                for lesson in lessons
                if start.isoformat() <= lesson["date"] <= end.isoformat()
            }
            if returned_ids and covered_days and ids_complete:
                removed, restored = await self.hass.async_add_executor_job(
                    storage.mark_removed_lessons, account_id, returned_ids, covered_days
                )

            # period/info for every lesson of this timetable pass without
            # lstext from the timetable response (Untis often only returns
            # it via the dedicated endpoint). Lehrstoff can still change
            # after it was entered, so a changed timetable asks for all.
            periods_needing_topic: list[dict[str, Any]] = [
                lesson
                for lesson in lessons
                if not lesson.get("lstext") and lesson.get("code") != "cancelled"
            ]
            # Plus: Stunden der letzten Tage bis heute, für die noch kein
            # Lehrstoff gespeichert ist — bei jedem Abruf, weil ein
            # Klassenbucheintrag getLatestImportTime nicht ändert.
            missing = await self.hass.async_add_executor_job(
                storage.lessons_missing_lstext,
                account_id,
                (today - timedelta(days=TOPIC_BACKFILL_DAYS)).isoformat(),
                today_iso,
            )
            queued = {lesson["untis_period_id"] for lesson in periods_needing_topic}
            backfill = [
                row for row in missing if row["untis_period_id"] not in queued
            ][:TOPIC_BACKFILL_MAX_PER_PULL]
            periods_needing_topic.extend(backfill)

            topic_fetched = 0
            topic_failed = 0
            topic_updates: list[dict[str, Any]] = []
            for lesson in periods_needing_topic:
                try:
                    info = await client.get_period_info(
                        day=date.fromisoformat(lesson["date"]),
                        start_time=lesson["start_time"],
                        end_time=lesson["end_time"],
                        period_id=lesson["untis_period_id"],
                        elem_id=elem_id,
                        elem_type=elem_type,
                    )
                except UntisApiError as err:
                    _LOGGER.debug(
                        "period/info failed for %s: %s",
                        lesson["untis_period_id"],
                        err,
                    )
                    topic_failed += 1
                    continue
                lstext = _extract_lstext(info)
                # Archive the full period/info payload even when empty —
                # it contains exam, attachments, lessonInfo etc. Only
                # touch lstext when we actually got a Lehrstoff body back,
                # so no-op fetches don't show up as spurious change events.
                # is_supervision_guess leitet storage aus Code und Lehrstoff ab.
                update: dict[str, Any] = {
                    "untis_period_id": lesson["untis_period_id"],
                    "date": lesson["date"],
                    "start_time": lesson["start_time"],
                    "end_time": lesson["end_time"],
                    "period_info_json": json.dumps(info, ensure_ascii=False, default=str),
                }
                if lstext:
                    update["lstext"] = lstext
                    topic_fetched += 1
                topic_updates.append(update)
            if topic_updates:
                await self.hass.async_add_executor_job(
                    partial(storage.upsert_lessons, account_id, topic_updates, today=today_iso)
                )

            try:
                raw_homework = await client.get_homework(homework_start, homework_end)
            except UntisApiError as err:
                _LOGGER.warning("Hausaufgaben-Abruf fehlgeschlagen: %s", err)
                raw_homework = {}
            hw_items = list(collect_homework(raw_homework))
            hw_results = await self.hass.async_add_executor_job(
                storage.upsert_homeworks, account_id, hw_items
            )
            hw_inserted, hw_updated, hw_unchanged = _count(
                hw_results, "inserted", "updated", "unchanged"
            )

            absences_ok = False
            try:
                raw_absences = await client.get_absences(
                    absence_start, absence_end, student_id=elem_id
                )
                absences_ok = True
            except UntisApiError as err:
                _LOGGER.warning("Fehlzeiten-Abruf fehlgeschlagen: %s", err)
                raw_absences = {}
            abs_items = list(collect_absences(raw_absences))
            abs_results = await self.hass.async_add_executor_job(
                storage.upsert_absences, account_id, abs_items
            )
            abs_inserted, abs_updated, abs_unchanged = _count(
                abs_results, "inserted", "updated", "unchanged"
            )
            changed_absence_ids = [
                item["untis_absence_id"]
                for item, res in zip(abs_items, abs_results)
                if res in ("inserted", "updated")
            ]

            # Master / Stammdaten — refreshed once per pull cycle and
            # accumulated across the entire school career. Mid-year
            # changes (Klassenlehrer-Wechsel durch Langzeiterkrankung,
            # Klassenwechsel, Wiederholung der Jahrgangsstufe) hinterlassen
            # einen Snapshot in master_snapshots; die Enrollment-Tabelle
            # bildet die (Schuljahr × Klasse)-Historie pro Kind ab.
            schoolyear_id: int | None = None
            schoolyear_start: str | None = None
            try:
                schoolyear = await client.get_current_schoolyear()
                await self.hass.async_add_executor_job(
                    storage.upsert_schoolyear, account_id, schoolyear
                )
                if isinstance(schoolyear, dict) and schoolyear.get("id"):
                    schoolyear_id = int(schoolyear["id"])
                    schoolyear_start = to_iso_date(schoolyear.get("startDate"))
            except UntisApiError as err:
                _LOGGER.warning("Schuljahr-Abruf fehlgeschlagen: %s", err)
            except (TypeError, ValueError) as err:
                _LOGGER.warning("Schuljahr unlesbar: %s", err)

            # Von der Schule gelöschte Fehlzeiten: nur nach erfolgreichem
            # Abruf mit Einträgen, nur im laufenden Schuljahr (ob der
            # Endpunkt ältere liefert, ist offen) und nur wenige je Abruf.
            deleted_span: tuple[str, str] | None = None
            returned_absence_ids = absence_ids_in_payload(raw_absences) if absences_ok else None
            if returned_absence_ids and schoolyear_start:
                deleted_span = await self.hass.async_add_executor_job(
                    partial(
                        storage.delete_absences_not_in,
                        account_id,
                        returned_absence_ids,
                        max(absence_start.isoformat(), schoolyear_start),
                        absence_end.isoformat(),
                        max_delete=ABSENCE_MAX_DELETIONS_PER_PULL,
                    )
                )

            # Re-derive was_absent for every lesson in the pulled window
            # plus the span of every new, changed or removed absence, so a
            # late-arriving absence also marks lessons outside the window.
            lo, hi = start.isoformat(), end.isoformat()
            changed_span = await self.hass.async_add_executor_job(
                storage.absence_span, account_id, changed_absence_ids
            )
            for span in (changed_span, deleted_span):
                if span:
                    lo, hi = min(lo, span[0]), max(hi, span[1])
            flagged_absent = await self.hass.async_add_executor_job(
                storage.recompute_attendance, account_id, lo, hi
            )

            try:
                teachers = await client.get_teachers()
                await self.hass.async_add_executor_job(
                    storage.upsert_teachers, account_id, teachers
                )
            except UntisApiError as err:
                _LOGGER.warning("Lehrer-Master-Abruf fehlgeschlagen: %s", err)

            try:
                klassen = await client.get_klassen()
                await self.hass.async_add_executor_job(
                    storage.upsert_own_klasse,
                    account_id,
                    klassen,
                    session.klasse_id,
                )
            except UntisApiError as err:
                _LOGGER.warning("Klassen-Master-Abruf fehlgeschlagen: %s", err)

            try:
                holidays = await client.get_holidays()
                await self.hass.async_add_executor_job(
                    storage.upsert_holidays, account_id, holidays
                )
            except UntisApiError as err:
                _LOGGER.warning("Ferien-Abruf fehlgeschlagen: %s", err)

            await self.hass.async_add_executor_job(
                storage.record_enrollment,
                account_id,
                schoolyear_id,
                session.klasse_id,
            )

            # Den Zeitstempel übernehmen, auch wenn einzelne Lehrstoff-Abrufe
            # scheiterten: Sonst holte jeder Abruf den ganzen Stundenplan samt
            # allen Lehrstoff-Abfragen neu, solange eine Stunde hängt. Fehlender
            # Lehrstoff der letzten Tage kommt über den Nachlauf oben.
            if latest_import is not None:
                await self.hass.async_add_executor_job(
                    storage.set_latest_import_time,
                    account_id,
                    latest_import,
                )

            # Mark this account as having completed a full pull so the
            # next cycle can flag retroactive additions.
            await self.hass.async_add_executor_job(
                storage.mark_pull_complete, account_id
            )

            _LOGGER.info(
                "Pull %s: lessons %d/%d/%d (new/upd/same), removed %d, restored %d, "
                "topics %d (fail %d, backfill %d), homework %d/%d/%d, "
                "absences %d/%d/%d, attendance flagged=%d",
                self._entry.title,
                inserted,
                updated,
                unchanged,
                removed,
                restored,
                topic_fetched,
                topic_failed,
                len(backfill),
                hw_inserted,
                hw_updated,
                hw_unchanged,
                abs_inserted,
                abs_updated,
                abs_unchanged,
                flagged_absent,
            )

            return {
                "lessons": {
                    "inserted": inserted,
                    "updated": updated,
                    "unchanged": unchanged,
                    "removed": removed,
                    "restored": restored,
                },
                "topics": {
                    "fetched": topic_fetched,
                    "failed": topic_failed,
                    "backfill": len(backfill),
                },
                "homework": {
                    "inserted": hw_inserted,
                    "updated": hw_updated,
                    "unchanged": hw_unchanged,
                },
                "absences": {
                    "inserted": abs_inserted,
                    "updated": abs_updated,
                    "unchanged": abs_unchanged,
                    "deleted": deleted_span is not None,
                },
                "attendance": {"flagged_absent": flagged_absent},
            }
        finally:
            await client.close()


def _extract_lstext(period_info: dict[str, Any]) -> str:
    """Pull the lesson topic body out of the /api/public/period/info payload.

    The shape we see on the Schule instance is::

        {"data": {"blocks": [[{"lessonTopic": {"text": "..."}, ...}]]}}

    `blocks` is a list of block-rows (one per parallel lesson grouping);
    each row is a list of period blocks. We take the first non-empty
    lessonTopic.text we encounter and also accept a few legacy shapes as
    a fallback.
    """
    if not isinstance(period_info, dict):
        return ""
    data = period_info.get("data") if isinstance(period_info.get("data"), dict) else period_info
    if not isinstance(data, dict):
        return ""

    # Primary: data.blocks[*][*].lessonTopic.text
    blocks = data.get("blocks")
    if isinstance(blocks, list):
        for row in blocks:
            items = row if isinstance(row, list) else [row]
            for block in items:
                if not isinstance(block, dict):
                    continue
                topic = block.get("lessonTopic")
                if isinstance(topic, dict):
                    text = (topic.get("text") or "").strip()
                    if text:
                        return text

    # Legacy / alternative shapes seen in other WebUntis versions.
    for key in ("lessonTopic", "lstext", "topic", "lesson_text"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for inner in ("text", "value", "topic"):
                v = value.get(inner)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return ""
