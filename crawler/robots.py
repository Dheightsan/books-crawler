"""robots.txt checks with one cached parser per host."""

import logging
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


class RobotsCache:
    def __init__(self, client: httpx.Client, user_agent: str):
        self.client = client
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    def _load(self, base: str) -> RobotFileParser | None:
        """None means no usable robots.txt, which allows everything."""
        try:
            resp = self.client.get(f"{base}/robots.txt")
        except httpx.HTTPError as exc:
            log.warning("robots.txt fetch failed for %s: %s", base, exc)
            return None
        if resp.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._parsers:
            self._parsers[base] = self._load(base)
        parser = self._parsers[base]
        if parser is None:
            return True
        ok = parser.can_fetch(self.user_agent, url)
        if not ok:
            log.info("skipping %s (disallowed by robots.txt)", url)
        return ok
