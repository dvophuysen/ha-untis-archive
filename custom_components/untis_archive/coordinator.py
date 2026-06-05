"""DataUpdateCoordinator that pulls WebUntis and persists into SQLite."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UntisApiError, UntisAuthError, UntisClient
from .const import (
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
    UPDATE_INTERVAL_HOURS,
    WINDOW_DAYS_BACK,
    WINDOW_DAYS_FORWARD,
)
from .storage import (
    UntisStorage,
    collect_absences,
    collect_homework,
    normalize_period,
)

_LOGGER = logging.getLogger(__name__)


class UntisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the timetable ±14 days every hour and stores everything."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
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
        if self._storage is not None:
            await self.hass.async_add_executor_job(self._storage.close)
            self._storage = None

    async def _async_update_data(self) -> dict[str, Any]:
        data = self._entry.data
        today = date.today()
        start = today - timedelta(days=WINDOW_DAYS_BACK)
        end = today + timedelta(days=WINDOW_DAYS_FORWARD)
        absence_start = today - timedelta(days=ABSENCE_WINDOW_DAYS_BACK)
        absence_end = today + timedelta(days=ABSENCE_WINDOW_DAYS_FORWARD)

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
                raise UpdateFailed(f"WebUntis-Login fehlgeschlagen: {err}") from err

            elem_id = data.get(CONF_STUDENT_ID) or session.person_id
            elem_type = session.person_type

            try:
                raw_timetable = await client.get_timetable(
                    start, end, elem_id=elem_id, elem_type=elem_type
                )
            except UntisApiError as err:
                raise UpdateFailed(f"Stundenplan-Abruf fehlgeschlagen: {err}") from err

            inserted = updated = unchanged = 0
            periods_needing_topic: list[dict[str, Any]] = []
            for raw in raw_timetable:
                try:
                    lesson = normalize_period(raw)
                except (KeyError, TypeError, ValueError) as err:
                    _LOGGER.debug("Skip malformed period %r: %s", raw, err)
                    continue
                result = await self.hass.async_add_executor_job(
                    self.storage.upsert_lesson, self.account_id, lesson
                )
                if result.action == "inserted":
                    inserted += 1
                elif result.action == "updated":
                    updated += 1
                else:
                    unchanged += 1
                # Fetch period/info only when we don't yet have lstext from
                # the timetable response (Untis often only returns it via
                # the dedicated endpoint).
                if not lesson.get("lstext") and lesson.get("code") != "cancelled":
                    periods_needing_topic.append(lesson)

            topic_fetched = 0
            topic_failed = 0
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
                # touch lstext / supervision_guess when we actually got
                # a Lehrstoff body back, so no-op fetches don't show up
                # as spurious change events.
                update: dict[str, Any] = {
                    "untis_period_id": lesson["untis_period_id"],
                    "date": lesson["date"],
                    "start_time": lesson["start_time"],
                    "end_time": lesson["end_time"],
                    "period_info_json": json.dumps(info, ensure_ascii=False, default=str),
                }
                if lstext:
                    update["lstext"] = lstext
                    update["is_supervision_guess"] = bool(
                        lesson["code"] == "irregular" and not lstext
                    )
                    topic_fetched += 1
                await self.hass.async_add_executor_job(
                    self.storage.upsert_lesson, self.account_id, update
                )

            hw_inserted = hw_updated = hw_unchanged = 0
            try:
                raw_homework = await client.get_homework(start, end)
            except UntisApiError as err:
                _LOGGER.warning("Hausaufgaben-Abruf fehlgeschlagen: %s", err)
                raw_homework = {}

            for hw in collect_homework(raw_homework):
                try:
                    result_str = await self.hass.async_add_executor_job(
                        self.storage.upsert_homework, self.account_id, hw
                    )
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("homework upsert failed for %r", hw, exc_info=True)
                    continue
                if result_str == "inserted":
                    hw_inserted += 1
                elif result_str == "updated":
                    hw_updated += 1
                else:
                    hw_unchanged += 1

            abs_inserted = abs_updated = 0
            try:
                raw_absences = await client.get_absences(absence_start, absence_end)
            except UntisApiError as err:
                _LOGGER.warning("Fehlzeiten-Abruf fehlgeschlagen: %s", err)
                raw_absences = {}

            for absence in collect_absences(raw_absences):
                try:
                    res = await self.hass.async_add_executor_job(
                        self.storage.upsert_absence, self.account_id, absence
                    )
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("absence upsert failed for %r", absence, exc_info=True)
                    continue
                if res == "inserted":
                    abs_inserted += 1
                elif res == "updated":
                    abs_updated += 1

            # Re-derive was_absent for every lesson in the pulled window so
            # newly arrived absences immediately propagate to the sensors.
            flagged_absent = await self.hass.async_add_executor_job(
                self.storage.recompute_attendance,
                self.account_id,
                start.isoformat(),
                end.isoformat(),
            )

            # Mark this account as having completed a full pull so the
            # next cycle can flag retroactive additions.
            await self.hass.async_add_executor_job(
                self.storage.mark_pull_complete, self.account_id
            )

            _LOGGER.info(
                "Pull %s: lessons %d/%d/%d (new/upd/same), topics %d (fail %d), "
                "homework %d/%d/%d, absences %d/%d, attendance flagged=%d",
                self._entry.title,
                inserted,
                updated,
                unchanged,
                topic_fetched,
                topic_failed,
                hw_inserted,
                hw_updated,
                hw_unchanged,
                abs_inserted,
                abs_updated,
                flagged_absent,
            )

            return {
                "lessons": {"inserted": inserted, "updated": updated, "unchanged": unchanged},
                "topics": {"fetched": topic_fetched, "failed": topic_failed},
                "homework": {
                    "inserted": hw_inserted,
                    "updated": hw_updated,
                    "unchanged": hw_unchanged,
                },
                "absences": {"inserted": abs_inserted, "updated": abs_updated},
                "attendance": {"flagged_absent": flagged_absent},
            }
        finally:
            await client.close()


def _extract_lstext(period_info: dict[str, Any]) -> str:
    """Pull the lesson topic body out of the /api/public/period/info payload.

    The shape we see on the GaW instance is::

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
