"""UNTIS Archive – Home Assistant custom component."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DB_SUBDIR, DOCS_SUBDIR, DOMAIN
from .coordinator import UntisCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "calendar"]

SERVICE_EXPORT_MARKDOWN = "export_markdown"
SERVICE_MARK_LESSON = "mark_lesson"

EXPORT_SCHEMA = vol.Schema(
    {
        vol.Required("account"): cv.string,
        vol.Optional("subject"): cv.string,
    }
)

MARK_SCHEMA = vol.Schema(
    {
        vol.Required("lesson_id"): vol.Coerce(int),
        vol.Optional("lstext"): cv.string,
        vol.Optional("is_supervision"): cv.boolean,
    }
)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "kind"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = UntisCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    bucket = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if bucket:
        coordinator: UntisCoordinator = bucket["coordinator"]
        await coordinator.async_shutdown()
    return unload_ok


def _find_coordinator_by_title(hass: HomeAssistant, title: str) -> UntisCoordinator | None:
    for bucket in hass.data.get(DOMAIN, {}).values():
        coord: UntisCoordinator = bucket["coordinator"]
        if coord.config_entry is not None and coord.config_entry.title == title:
            return coord
        # Fall back to matching via the coordinator name we set.
        if coord.name.endswith(f":{title}"):
            return coord
    return None


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_EXPORT_MARKDOWN):
        return

    async def export_markdown(call: ServiceCall) -> None:
        title = call.data["account"]
        subject_filter = call.data.get("subject")
        coordinator = _find_coordinator_by_title(hass, title)
        if coordinator is None:
            raise HomeAssistantError(f"Kein UNTIS-Account mit Anzeigename '{title}'.")

        rows = await hass.async_add_executor_job(
            coordinator.storage.lessons_between,
            coordinator.account_id,
            "0001-01-01",
            "9999-12-31",
        )

        out_root = Path(hass.config.path(DB_SUBDIR, DOCS_SUBDIR, _slug(title)))
        out_root.mkdir(parents=True, exist_ok=True)

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            subj = row.get("subject_name") or "Unbekanntes Fach"
            if subject_filter and subj != subject_filter:
                continue
            grouped.setdefault(subj, []).append(row)

        def _write() -> None:
            for subj, items in grouped.items():
                items_sorted = sorted(
                    items,
                    key=lambda r: (r.get("date") or "", r.get("start_time") or 0),
                    reverse=True,
                )
                lines: list[str] = [f"# {subj} – {title}", ""]
                for r in items_sorted:
                    text = r.get("lstext_manual_override") or r.get("lstext") or ""
                    code = r.get("code") or ""
                    status_bits = []
                    if code:
                        status_bits.append(code)
                    if r.get("supervision_manual_override") or r.get("is_supervision_guess"):
                        status_bits.append("Aufsicht")
                    status = f" _({', '.join(status_bits)})_" if status_bits else ""
                    lines.append(f"## {r['date']} – {r['start_time']:04d}{status}")
                    if text:
                        lines.append(text)
                    else:
                        lines.append("_(kein Lehrstoff eingetragen)_")
                    lines.append("")
                slug = _slug(subj)
                (out_root / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")

        await hass.async_add_executor_job(_write)
        _LOGGER.info("Exported %d subjects for %s to %s", len(grouped), title, out_root)

    async def mark_lesson(call: ServiceCall) -> None:
        lesson_id = call.data["lesson_id"]
        lstext = call.data.get("lstext")
        is_supervision = call.data.get("is_supervision")

        # mark_lesson works against the shared DB; pick any coordinator.
        bucket = next(iter(hass.data.get(DOMAIN, {}).values()), None)
        if bucket is None:
            raise HomeAssistantError("UNTIS Archive ist nicht eingerichtet.")
        coordinator: UntisCoordinator = bucket["coordinator"]
        await hass.async_add_executor_job(
            coordinator.storage.mark_lesson,
            lesson_id,
            lstext,
            is_supervision,
        )
        # Trigger a refresh so sensors update.
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_EXPORT_MARKDOWN, export_markdown, schema=EXPORT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_LESSON, mark_lesson, schema=MARK_SCHEMA
    )
