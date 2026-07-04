"""Yahoo crumb/cookie auth for quoteSummary endpoints.

Yahoo periodically changes or invalidates crumbs. This module treats crumb
failure as a data-availability issue, not an API failure for callers.
"""
import logging
from threading import Lock
from typing import Any

import httpx

from ..config import YAHOO_COOKIE_URL, YAHOO_CRUMB_URL

logger = logging.getLogger(__name__)

_lock = Lock()
_cookies: dict[str, str] | None = None
_crumb: str | None = None


def invalidate() -> None:
    global _cookies, _crumb
    with _lock:
        _cookies = None
        _crumb = None


def _apply_cookies(client: httpx.Client) -> None:
    if not _cookies:
        return
    for name, value in _cookies.items():
        client.cookies.set(name, value)


def get_crumb(client: httpx.Client) -> str | None:
    global _cookies, _crumb
    with _lock:
        if _crumb:
            _apply_cookies(client)
            return _crumb

        try:
            client.get(YAHOO_COOKIE_URL)
            crumb_response = client.get(YAHOO_CRUMB_URL)
            crumb_response.raise_for_status()
        except Exception as exc:
            logger.warning("Yahoo crumb fetch failed: %s", type(exc).__name__)
            _cookies = None
            _crumb = None
            return None

        crumb = crumb_response.text.strip()
        if not crumb:
            logger.warning("Yahoo crumb fetch returned an empty crumb")
            _cookies = None
            _crumb = None
            return None

        _cookies = {cookie.name: cookie.value for cookie in client.cookies.jar}
        _crumb = crumb
        return _crumb


def _invalid_crumb(response: httpx.Response) -> bool:
    if response.status_code == 401:
        return True
    try:
        return "Invalid Crumb" in response.text
    except Exception:
        return False


def authed_get(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
) -> httpx.Response | None:
    request_params = dict(params or {})
    crumb = get_crumb(client)
    if not crumb:
        return None
    request_params["crumb"] = crumb
    _apply_cookies(client)

    for attempt in range(2):
        try:
            response = client.get(url, params=request_params)
        except Exception as exc:
            logger.warning("Yahoo authed request failed: %s", type(exc).__name__)
            return None

        if attempt == 0 and _invalid_crumb(response):
            invalidate()
            crumb = get_crumb(client)
            if not crumb:
                return None
            request_params["crumb"] = crumb
            _apply_cookies(client)
            continue
        return response
    return None
