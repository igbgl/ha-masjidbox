"""Data coordinator for MasjidBox."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    MasjidboxApiError,
    MasjidboxAuthError,
    MasjidboxClient,
    MasjidboxConnectionError,
    discover_credentials,
)
from .const import (
    CONF_API_BASE,
    CONF_API_KEY,
    CONF_BUNDLE_URL,
    CONF_DAYS,
    CONF_INCLUDE_RAW,
    CONF_POLL_INTERVAL,
    CONF_UNIQUE_ID,
    DEFAULT_DAYS,
    DEFAULT_INCLUDE_RAW,
    DEFAULT_POLL_INTERVAL_MINUTES,
    DOMAIN,
    TIME_SENSOR_KEYS,
)

_LOGGER = logging.getLogger(__name__)


def _parse_iso(dt_str: str | None) -> datetime | None:
    if not dt_str or not isinstance(dt_str, str):
        return None
    parsed = dt_util.parse_datetime(dt_str)
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt_util.as_utc(parsed)


def _first_jumuah_time(
    row: dict[str, Any],
    *,
    iqamah: bool,
) -> datetime | None:
    if iqamah:
        iq = row.get("iqamah")
        if not isinstance(iq, dict):
            return None
        raw = iq.get("jumuah")
    else:
        raw = row.get("jumuah")
    if isinstance(raw, list) and raw:
        return _parse_iso(str(raw[0]))
    if isinstance(raw, str):
        return _parse_iso(raw)
    return None


def _pick_today_row(
    timetable: list[Any],
) -> dict[str, Any] | None:
    today_local = dt_util.now().date()
    for row in timetable:
        if not isinstance(row, dict):
            continue
        date_s = row.get("date")
        if not date_s:
            continue
        row_dt = _parse_iso(str(date_s))
        if row_dt is None:
            continue
        if dt_util.as_local(row_dt).date() == today_local:
            return row
    return None


def _build_times_dict(
    row: dict[str, Any],
) -> dict[str, datetime | None]:
    """Map sensor keys to UTC datetime for today's row."""
    iq = row.get("iqamah") if isinstance(row.get("iqamah"), dict) else {}

    out: dict[str, datetime | None] = {
        "fajr_adhan": _parse_iso(row.get("fajr")),
        "fajr_iqamah": _parse_iso(iq.get("fajr")) if iq else None,
        "sunrise": _parse_iso(row.get("sunrise")),
        "dhuhr_adhan": _parse_iso(row.get("dhuhr")),
        "dhuhr_iqamah": _parse_iso(iq.get("dhuhr")) if iq else None,
        "asr_adhan": _parse_iso(row.get("asr")),
        "asr_iqamah": _parse_iso(iq.get("asr")) if iq else None,
        "maghrib_adhan": _parse_iso(row.get("maghrib")),
        "maghrib_iqamah": _parse_iso(iq.get("maghrib")) if iq else None,
        "isha_adhan": _parse_iso(row.get("isha")),
        "isha_iqamah": _parse_iso(iq.get("isha")) if iq else None,
        "jumuah_adhan": _first_jumuah_time(row, iqamah=False),
        "jumuah_iqamah": _first_jumuah_time(row, iqamah=True),
    }
    return out


class MasjidboxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for MasjidBox prayer data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MasjidboxClient,
    ) -> None:
        poll_minutes = entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_MINUTES
        )
        try:
            pm = int(poll_minutes)
        except (TypeError, ValueError):
            pm = DEFAULT_POLL_INTERVAL_MINUTES
        interval_sec = max(60, pm * 60)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_sec),
        )
        self.entry = entry
        self.client = client

    def _days(self) -> int:
        d = self.entry.options.get(CONF_DAYS, DEFAULT_DAYS)
        try:
            n = int(d)
        except (TypeError, ValueError):
            return DEFAULT_DAYS
        return max(1, min(14, n))

    def _include_raw(self) -> bool:
        return bool(self.entry.options.get(CONF_INCLUDE_RAW, DEFAULT_INCLUDE_RAW))

    async def _rediscover_and_persist(self) -> None:
        session = async_get_clientsession(self.hass)
        api_base, api_key, bundle_url = await discover_credentials(
            session, self.entry.data[CONF_UNIQUE_ID]
        )
        new_data = {
            **self.entry.data,
            CONF_API_BASE: api_base,
            CONF_API_KEY: api_key,
            CONF_BUNDLE_URL: bundle_url,
        }
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        self.client.set_credentials(api_base, api_key)
        _LOGGER.info("MasjidBox credentials re-discovered and saved")

    async def _async_update_data(self) -> dict[str, Any]:
        begin = dt_util.start_of_local_day()
        begin_iso = dt_util.as_local(begin).isoformat()
        days = self._days()

        try:
            payload = await self.client.fetch_timetable(begin_iso, days)
        except MasjidboxAuthError as err:
            _LOGGER.warning("MasjidBox auth failed, attempting re-discovery: %s", err)
            try:
                await self._rediscover_and_persist()
                payload = await self.client.fetch_timetable(begin_iso, days)
            except MasjidboxApiError as err2:
                raise UpdateFailed(f"MasjidBox API error after re-discovery: {err2}") from err2

        except MasjidboxConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except MasjidboxApiError as err:
            raise UpdateFailed(str(err)) from err

        timetable = payload.get("timetable")
        if not isinstance(timetable, list):
            raise UpdateFailed("Invalid timetable in response")

        row = _pick_today_row(timetable)
        if row is None:
            _LOGGER.warning(
                "No timetable row matched local today; sensors may be empty"
            )
            times = {k: None for k in TIME_SENSOR_KEYS}
        else:
            times = _build_times_dict(row)

        result: dict[str, Any] = {
            "unique_id": self.entry.data[CONF_UNIQUE_ID],
            "masjid_name": payload.get("name"),
            "address": payload.get("address"),
            "times": times,
            "today_row": row,
        }
        if self._include_raw():
            result["raw"] = payload
        return result
