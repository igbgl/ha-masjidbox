"""Config flow for MasjidBox."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import (
    MasjidboxApiError,
    MasjidboxAuthError,
    MasjidboxClient,
    MasjidboxConnectionError,
    MasjidboxDiscoveryError,
    discover_credentials,
)
from .const import (
    CONF_API_BASE,
    CONF_API_KEY,
    CONF_BUNDLE_URL,
    CONF_DAYS,
    CONF_INCLUDE_RAW,
    CONF_POLL_INTERVAL,
    CONF_REDISCOVER_ON_RELOAD,
    CONF_UNIQUE_ID,
    DEFAULT_DAYS,
    DEFAULT_INCLUDE_RAW,
    DEFAULT_POLL_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UNIQUE_ID): str,
    }
)


class MasjidboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """MasjidBox config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = user_input[CONF_UNIQUE_ID].strip()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            try:
                api_base, api_key, bundle_url = await discover_credentials(
                    session, unique_id
                )
            except MasjidboxDiscoveryError as err:
                msg = str(err)
                if msg == "prayer_times_not_found":
                    errors["base"] = "invalid_unique_id"
                else:
                    errors["base"] = "discovery_failed"
            except MasjidboxConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("MasjidBox discovery failed")
                errors["base"] = "unknown"
            else:
                client = MasjidboxClient(session, api_base, api_key, unique_id)
                begin_iso = dt_util.as_local(dt_util.start_of_local_day()).isoformat()
                try:
                    await client.fetch_timetable(begin_iso, DEFAULT_DAYS)
                except MasjidboxAuthError:
                    errors["base"] = "invalid_auth"
                except MasjidboxConnectionError:
                    errors["base"] = "cannot_connect"
                except MasjidboxApiError:
                    errors["base"] = "unknown"
                except Exception:
                    _LOGGER.exception("MasjidBox API validation failed")
                    errors["base"] = "unknown"
                else:
                    title = f"MasjidBox ({unique_id})"
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_UNIQUE_ID: unique_id,
                            CONF_API_BASE: api_base,
                            CONF_API_KEY: api_key,
                            CONF_BUNDLE_URL: bundle_url,
                        },
                        options={
                            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL_MINUTES,
                            CONF_DAYS: DEFAULT_DAYS,
                            CONF_REDISCOVER_ON_RELOAD: False,
                            CONF_INCLUDE_RAW: DEFAULT_INCLUDE_RAW,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return MasjidboxOptionsFlow()


class MasjidboxOptionsFlow(OptionsFlow):
    """Options for MasjidBox."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_MINUTES
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=24 * 60)),
                    vol.Optional(
                        CONF_DAYS,
                        default=self.config_entry.options.get(CONF_DAYS, DEFAULT_DAYS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
                    vol.Optional(
                        CONF_REDISCOVER_ON_RELOAD,
                        default=self.config_entry.options.get(
                            CONF_REDISCOVER_ON_RELOAD, False
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_INCLUDE_RAW,
                        default=self.config_entry.options.get(
                            CONF_INCLUDE_RAW, DEFAULT_INCLUDE_RAW
                        ),
                    ): bool,
                }
            ),
        )
