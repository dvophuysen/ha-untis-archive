"""Config flow with live credential validation against WebUntis.

UX choices:

- Previously entered values (except the password) are pre-filled when the
  form is shown again after an error – the user can fix a typo without
  retyping everything.
- The raw WebUntis error message is shown inside the form via
  ``description_placeholders``, so the user can tell *which* field is
  wrong instead of just seeing "Login failed".
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
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
    INVALID_CREDENTIALS,
)

_LOGGER = logging.getLogger(__name__)


# WebUntis JSON-RPC error codes we want to translate into specific
# user-facing messages. Anything not in this map falls back to the generic
# ``invalid_auth`` plus the raw server message in the description.
_ERR_CODES = {
    INVALID_CREDENTIALS: "invalid_credentials",
    -8500: "invalid_school",       # no such school
    -8502: "invalid_school",       # ambiguous / not found
    -8998: "too_many_requests",
}


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DISPLAY_NAME, default=defaults.get(CONF_DISPLAY_NAME, "")
            ): str,
            vol.Required(
                CONF_SERVER,
                default=defaults.get(CONF_SERVER, ""),
            ): str,
            vol.Required(
                CONF_SCHOOL, default=defaults.get(CONF_SCHOOL, "")
            ): str,
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_STUDENT_ID,
                description={"suggested_value": defaults.get(CONF_STUDENT_ID)},
            ): int,
        }
    )


class UntisArchiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error_detail": ""}
        defaults: dict[str, Any] = dict(user_input or {})

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
                _LOGGER.warning("Login validation failed: %s (code=%s)", err, err.code)
                placeholders["error_detail"] = str(err)
                errors["base"] = _ERR_CODES.get(err.code or 0, "invalid_auth")
            except UntisApiError as err:
                _LOGGER.warning("API error during validation: %s", err)
                placeholders["error_detail"] = str(err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during validation")
                placeholders["error_detail"] = repr(err)
                errors["base"] = "unknown"
            finally:
                await client.close()

            if not errors:
                # Strip the password before storing? No – HA stores config
                # entries securely; the password is needed for refreshes.
                return self.async_create_entry(
                    title=user_input[CONF_DISPLAY_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """WebUntis lehnt das gespeicherte Passwort ab: nur das neue abfragen."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error_detail": "", "account": entry.title}
        if user_input is not None:
            client = UntisClient(
                entry.data[CONF_SERVER],
                entry.data[CONF_SCHOOL],
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.login()
            except UntisAuthError as err:
                placeholders["error_detail"] = str(err)
                errors["base"] = _ERR_CODES.get(err.code or 0, "invalid_auth")
            except UntisApiError as err:
                placeholders["error_detail"] = str(err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reauth")
                placeholders["error_detail"] = repr(err)
                errors["base"] = "unknown"
            finally:
                await client.close()
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders=placeholders,
        )
