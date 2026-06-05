"""Config flow with live credential validation against WebUntis."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import UntisApiError, UntisAuthError, UntisClient
from .const import (
    CONF_DISPLAY_NAME,
    CONF_PASSWORD,
    CONF_SCHOOL,
    CONF_SERVER,
    CONF_STUDENT_ID,
    CONF_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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
        errors: dict[str, str] = {}

        if user_input is not None:
            unique = (
                f"{user_input[CONF_USERNAME]}@"
                f"{user_input[CONF_SERVER]}/{user_input[CONF_SCHOOL]}"
            )
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()

            client = UntisClient(
                user_input[CONF_SERVER],
                user_input[CONF_SCHOOL],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.login()
            except UntisAuthError as err:
                _LOGGER.warning("Login validation failed: %s", err)
                errors["base"] = "invalid_auth"
            except UntisApiError as err:
                _LOGGER.warning("API error during validation: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during validation")
                errors["base"] = "unknown"
            finally:
                await client.close()

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_DISPLAY_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
