"""MasjidBox discovery and API client."""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp

from .const import API_GET_PARAM, MASJIDBOX_ORIGIN, PRAYER_TIMES_PATH

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; HomeAssistant-MasjidBox/1.0; +https://www.home-assistant.io/)"
)

# Main app bundle: /public/<digits>.<hex>.app.js (exclude chunks like a4420871.app.js)
_MAIN_APP_JS_PATH = re.compile(r"^/public/\d+\.[a-f0-9]+\.app\.js$", re.I)

_API_RE = re.compile(r'masjidboxAPI\s*:\s*"([^"]+)"')
_KEY_RE = re.compile(r'masjidboxKEY\s*:\s*"([^"]+)"')


class MasjidboxApiError(Exception):
    """Base API error."""


class MasjidboxAuthError(MasjidboxApiError):
    """Invalid or expired API key."""


class MasjidboxConnectionError(MasjidboxApiError):
    """Network or HTTP error."""


class MasjidboxDiscoveryError(MasjidboxApiError):
    """Could not parse HTML/JS for credentials."""


class _ScriptSrcCollector(HTMLParser):
    """Collect script src attributes in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        for name, value in attrs:
            if name == "src" and value:
                self.srcs.append(value.strip())
                break


def _normalize_script_url(src: str) -> str:
    return src if src.startswith("http") else urljoin(MASJIDBOX_ORIGIN, src)


def _pick_main_bundle_url(script_srcs: list[str]) -> str | None:
    for src in script_srcs:
        full = _normalize_script_url(src)
        parsed = urlparse(full)
        allowed_hosts = ("masjidbox.com", "www.masjidbox.com")
        if parsed.netloc not in ("", *allowed_hosts):
            continue
        path = parsed.path or ""
        if _MAIN_APP_JS_PATH.match(path):
            return full
    return None


async def discover_credentials(
    session: aiohttp.ClientSession,
    unique_id: str,
) -> tuple[str, str, str]:
    """Fetch prayer-times page and JS bundle; return (api_base, api_key, bundle_url).

    Raises:
        MasjidboxConnectionError: HTTP/network failure.
        MasjidboxDiscoveryError: Could not find bundle or extract credentials.
    """
    page_url = f"{MASJIDBOX_ORIGIN}{PRAYER_TIMES_PATH}/{unique_id.strip()}"
    headers = {"User-Agent": USER_AGENT}

    try:
        async with session.get(page_url, headers=headers) as resp:
            if resp.status == 404:
                raise MasjidboxDiscoveryError("prayer_times_not_found")
            if resp.status != 200:
                text = await resp.text()
                raise MasjidboxConnectionError(
                    f"Landing page {resp.status}: {text[:200]}"
                )
            html = await resp.text()
    except aiohttp.ClientError as err:
        raise MasjidboxConnectionError(str(err)) from err

    collector = _ScriptSrcCollector()
    try:
        collector.feed(html)
    except Exception as err:
        raise MasjidboxDiscoveryError("html_parse") from err

    bundle_url = _pick_main_bundle_url(collector.srcs)
    if not bundle_url:
        _LOGGER.debug("Script srcs seen: %s", collector.srcs[:20])
        raise MasjidboxDiscoveryError("no_app_bundle")

    try:
        async with session.get(bundle_url, headers=headers) as resp:
            if resp.status != 200:
                raise MasjidboxConnectionError(
                    f"Bundle HTTP {resp.status}"
                )
            js_body = await resp.text()
    except aiohttp.ClientError as err:
        raise MasjidboxConnectionError(str(err)) from err

    m_api = _API_RE.search(js_body)
    m_key = _KEY_RE.search(js_body)
    if not m_api or not m_key:
        raise MasjidboxDiscoveryError("missing_api_constants")

    api_base = m_api.group(1).rstrip("/")
    api_key = m_key.group(1)
    return api_base, api_key, bundle_url


class MasjidboxClient:
    """Low-level client for athany landing API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_base: str,
        api_key: str,
        unique_id: str,
    ) -> None:
        self._session = session
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._unique_id = unique_id.strip()

    def set_credentials(self, api_base: str, api_key: str) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key

    @property
    def unique_id(self) -> str:
        return self._unique_id

    async def fetch_timetable(
        self,
        begin_iso: str,
        days: int,
    ) -> dict[str, Any]:
        """GET landing athany JSON.

        Args:
            begin_iso: Local start-of-day ISO string with offset (URL-encoded by aiohttp).
            days: Number of days to request.

        Raises:
            MasjidboxAuthError: 401/403.
            MasjidboxConnectionError: Other HTTP/network errors.
            MasjidboxApiError: Invalid JSON or unexpected shape.
        """
        url = f"{self._api_base}/athany/{self._unique_id}"
        params = {"get": API_GET_PARAM, "days": str(days), "begin": begin_iso}
        headers = {
            "User-Agent": USER_AGENT,
            "apikey": self._api_key,
            "Accept": "application/json",
        }

        try:
            async with self._session.get(url, headers=headers, params=params) as resp:
                if resp.status in (401, 403):
                    raise MasjidboxAuthError(f"HTTP {resp.status}")
                if resp.status >= 400:
                    text = await resp.text()
                    raise MasjidboxConnectionError(
                        f"API error {resp.status}: {text[:300]}"
                    )
                try:
                    data: dict[str, Any] = await resp.json()
                except aiohttp.ContentTypeError as err:
                    raise MasjidboxApiError("Response is not JSON") from err
        except aiohttp.ClientError as err:
            raise MasjidboxConnectionError(str(err)) from err

        if not isinstance(data, dict) or "timetable" not in data:
            raise MasjidboxApiError("Unexpected API response shape")
        return data
