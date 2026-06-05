"""Config flow for UNTIS Archive.

Phase-A stub: collects credentials but does not yet validate them against
WebUntis. Validation will be added in Phase C together with the live
coordinator.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DISPLAY_NAME,
    CONF_PASSWORD,
    CONF_SCHOOL,
    CONF_SERVER,
    CONF_STUDENT_ID,
    CONF_USERNAME,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISPLAY_NAME): str,
        vol.Required(CONF_SERVER): str,
        vol.Required(CONF_SCHOOL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_STUDENT_ID): int,
    }
)


class UntisArchiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        # Allow multiple entries (one per child); de-dupe by user@server/school.
        unique = (
            f"{user_input[CONF_USERNAME]}@{user_input[CONF_SERVER]}/{user_input[CONF_SCHOOL]}"
        )
        await self.async_set_unique_id(unique)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_DISPLAY_NAME],
            data=user_input,
        )
