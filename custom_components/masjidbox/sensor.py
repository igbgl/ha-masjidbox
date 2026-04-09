"""Sensor platform for MasjidBox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_INCLUDE_RAW,
    CONF_UNIQUE_ID,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    TIME_SENSOR_KEYS,
)
from .coordinator import MasjidboxCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MasjidboxSensorEntityDescription(SensorEntityDescription):
    """MasjidBox timestamp sensor."""

    time_key: str


def _time_value(coordinator: MasjidboxCoordinator, key: str) -> datetime | None:
    data = coordinator.data
    if not data:
        return None
    times = data.get("times") or {}
    val = times.get(key)
    return val if isinstance(val, datetime) else None


SENSOR_DESCRIPTIONS: tuple[MasjidboxSensorEntityDescription, ...] = tuple(
    MasjidboxSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TIMESTAMP,
        time_key=key,
    )
    for key in TIME_SENSOR_KEYS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MasjidBox sensors."""
    coordinator: MasjidboxCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities(
        MasjidboxPrayerSensor(coordinator, desc, entry)
        for desc in SENSOR_DESCRIPTIONS
    )


class MasjidboxPrayerSensor(
    CoordinatorEntity[MasjidboxCoordinator], SensorEntity
):
    """Prayer time timestamp sensor."""

    entity_description: MasjidboxSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MasjidboxCoordinator,
        description: MasjidboxSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._unique_id_slug = entry.data[CONF_UNIQUE_ID]
        self._attr_unique_id = f"{DOMAIN}_{self._unique_id_slug}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        name = self.coordinator.data.get("masjid_name") if self.coordinator.data else None
        if not name:
            name = f"MasjidBox ({self._unique_id_slug})"
        return {
            "identifiers": {(DOMAIN, self._unique_id_slug)},
            "name": name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    @property
    def native_value(self) -> datetime | None:
        return _time_value(self.coordinator, self.entity_description.time_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        attrs: dict[str, Any] = {}
        addr = self.coordinator.data.get("address")
        if addr:
            attrs["address"] = addr
        # Avoid attaching the full API payload to every entity.
        if (
            self.entity_description.key == "fajr_adhan"
            and self.coordinator.entry.options.get(CONF_INCLUDE_RAW)
            and (raw := self.coordinator.data.get("raw"))
        ):
            attrs["raw"] = raw
        return attrs or None
