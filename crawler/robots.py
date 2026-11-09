"""robots.txt checks with one cached parser per host, following RFC 9309."""

import logging
import time
from collections.abc import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .fetch import get_with_retries

log = logging.getLogger(__name__)


class RobotsCache:
    """Per-host robots.txt rules.

    2xx: the file is parsed. 4xx other than 429: no rules, everything is allowed.
    5xx, 429 or a network error (after retries): the host is treated as disallow-all
    for the rest of the run.
    """

    def __init__(
        self,
        client: httpx.Client,
        user_agent: str,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.client = client
        self.user_agent = user_agent
        self.sleep = sleep
        self._parsers: dict[str, RobotFileParser] = {}

    def _load(self, base: str) -> RobotFileParser:
        url = f"{base}/robots.txt"
        parser = RobotFileParser()
        try:
            resp = get_with_retries(self.client, url, sleep=self.sleep)
        except httpx.RequestError as exc:
            log.warning(
                "%s: robots.txt unreachable (%s: %s), treating %s as disallowed for this run",
                url, type(exc).__name__, exc, base,
            )
            parser.disallow_all = True
            return parser
        status = resp.status_code
        if 200 <= status < 300:
            parser.parse(resp.text.splitlines())
        elif 400 <= status < 500 and status != 429:
            log.info("%s: HTTP %s, no robots.txt, everything allowed", url, status)
            parser.allow_all = True
        else:
            log.warning(
                "%s: HTTP %s after retries, treating %s as disallowed for this run",
                url, status, base,
            )
            parser.disallow_all = True
        return parser

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._parsers:
            self._parsers[base] = self._load(base)
        ok = self._parsers[base].can_fetch(self.user_agent, url)
        if not ok:
            log.info("skipping %s (disallowed by robots.txt)", url)
        return ok
