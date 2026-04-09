# Prayer times for Home Assistant

**Adhan**, **iqamah**, and **Jumuah** times from [MasjidBox](https://masjidbox.com/). Enter the masjid **unique ID** (URL slug), e.g. `islam-bgl` from `https://masjidbox.com/prayer-times/islam-bgl`.

## Features

- Discovers the public API base URL and embedded key from the site (no manual API key).
- Stores credentials in the config entry; routine updates **do not** re-download the JavaScript bundle.
- Re-runs discovery automatically if the API returns **401/403**, then retries.
- Optional **re-discover on reload** (off by default): fetches the bundle again when the integration reloads (e.g. after a Home Assistant restart).
- One **device** per masjid with **timestamp** sensors: Fajr, sunrise, Dhuhr, Asr, Maghrib, Isha (adhan + iqamah where available), plus Jumuah adhan and iqamah when present in the timetable.

## Disclaimer

**Not** an official product. It relies on public pages and patterns that may change. The embedded API key is meant for the web app; storing it in Home Assistant follows the same trust model as the browser. Use at your own risk. Respect [MasjidBox](https://masjidbox.com/) terms of use.

## Installation

Copy [`custom_components/masjidbox/`](custom_components/masjidbox/) into your `config/custom_components/` directory, or add this repository in HACS.

Restart Home Assistant, then **Settings → Devices & services → Add integration** and select this integration.

## Configuration

| Setting | Description |
|--------|-------------|
| **Masjid unique ID** | Slug from the prayer-times URL (required). |
| **Update interval** | Minutes between refreshes (default 30). |
| **API days window** | `days` query parameter (default 7; must include today). |
| **Re-discover API key on reload** | When enabled, runs HTML/JS discovery on each reload. |
| **Include raw API payload** | Adds the full JSON to the **Fajr adhan** sensor attributes (debug). |

## Debugging

```yaml
logger:
  default: info
  logs:
    custom_components.masjidbox: debug
```

## License

MIT License — see [LICENSE](LICENSE).
