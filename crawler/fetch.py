"""HTTP client with retries and backoff."""

import logging
import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime

import httpx

from . import USER_AGENT

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


def make_client(
    transport: httpx.BaseTransport | None = None, timeout: float = 15.0
) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
        transport=transport,
    )


def retry_after_seconds(value: str | None) -> float | None:
    """Parse a Retry-After header (seconds or HTTP date)."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def get_with_retries(
    client: httpx.Client,
    url: str,
    retries: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """GET with exponential backoff on 429 and 5xx. Retry-After wins when present."""
    attempt = 0
    while True:
        try:
            resp = client.get(url)
        except httpx.TransportError as exc:
            if attempt >= retries:
                raise
            wait = min(max_delay, base_delay * 2**attempt)
            log.warning("%s: %s, retrying in %.1fs", url, exc, wait)
        else:
            if resp.status_code not in RETRY_STATUS or attempt >= retries:
                return resp
            wait = retry_after_seconds(resp.headers.get("Retry-After"))
            if wait is None:
                wait = base_delay * 2**attempt
            wait = min(max_delay, wait)
            log.warning("%s: HTTP %s, retrying in %.1fs", url, resp.status_code, wait)
        sleep(wait)
        attempt += 1
