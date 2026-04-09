"""Constants for the MasjidBox integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "masjidbox"

MASJIDBOX_ORIGIN: Final = "https://masjidbox.com"
PRAYER_TIMES_PATH: Final = "/prayer-times"

# Config / options
CONF_UNIQUE_ID: Final = "unique_id"
CONF_API_BASE: Final = "api_base"
CONF_API_KEY: Final = "api_key"
CONF_BUNDLE_URL: Final = "bundle_url"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_DAYS: Final = "days"
CONF_REDISCOVER_ON_RELOAD: Final = "rediscover_on_reload"
CONF_INCLUDE_RAW: Final = "include_raw"

# Options store poll interval in minutes; coordinator converts to seconds.
DEFAULT_POLL_INTERVAL_MINUTES: Final = 30
DEFAULT_DAYS: Final = 7
DEFAULT_INCLUDE_RAW: Final = False

# API query
API_GET_PARAM: Final = "at"

MANUFACTURER: Final = "MasjidBox"
MODEL: Final = "Prayer times"

ATTRIBUTION: Final = "Data provided by MasjidBox (unofficial)"

TIME_SENSOR_KEYS: Final = (
    "fajr_adhan",
    "fajr_iqamah",
    "sunrise",
    "dhuhr_adhan",
    "dhuhr_iqamah",
    "asr_adhan",
    "asr_iqamah",
    "maghrib_adhan",
    "maghrib_iqamah",
    "isha_adhan",
    "isha_iqamah",
    "jumuah_adhan",
    "jumuah_iqamah",
)
