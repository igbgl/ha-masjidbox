"""The MasjidBox prayer times integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MasjidboxClient, discover_credentials
from .const import (
    CONF_API_BASE,
    CONF_API_KEY,
    CONF_BUNDLE_URL,
    CONF_REDISCOVER_ON_RELOAD,
    CONF_UNIQUE_ID,
    DOMAIN,
)
from .coordinator import MasjidboxCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MasjidBox from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    unique_id = entry.data[CONF_UNIQUE_ID]

    if entry.options.get(CONF_REDISCOVER_ON_RELOAD):
        try:
            api_base, api_key, bundle_url = await discover_credentials(
                session, unique_id
            )
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_API_BASE: api_base,
                    CONF_API_KEY: api_key,
                    CONF_BUNDLE_URL: bundle_url,
                },
            )
        except Exception:
            _LOGGER.exception(
                "MasjidBox re-discovery on reload failed; using stored credentials"
            )

    client = MasjidboxClient(
        session,
        entry.data[CONF_API_BASE],
        entry.data[CONF_API_KEY],
        unique_id,
    )
    coordinator = MasjidboxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MasjidBox config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
    return unload_ok


async def async_options_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
