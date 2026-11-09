"""Crawl loop: listing pages, then product pages, within a page budget."""

import logging
import time
from collections.abc import Callable, Iterator

import httpx

from . import USER_AGENT
from .fetch import get_with_retries
from .parse import Book, parse_category_links, parse_listing, parse_product
from .ratelimit import HostLimiter
from .robots import RobotsCache

log = logging.getLogger(__name__)


class Crawler:
    def __init__(
        self,
        client: httpx.Client,
        delay: float = 1.0,
        max_pages: int = 25,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.client = client
        self.max_pages = max_pages
        self.pages = 0
        self.sleep = sleep
        self.limiter = HostLimiter(delay, clock=clock, sleep=sleep)
        self.robots = RobotsCache(_Throttled(client, self.limiter), USER_AGENT, sleep=sleep)
        self.seen: set[str] = set()

    def _get(self, url: str) -> str | None:
        """Fetch one page if robots.txt, the budget and the status allow it."""
        if url in self.seen or self.pages >= self.max_pages:
            return None
        if not self.robots.allowed(url):
            return None
        self.seen.add(url)
        self.limiter.wait(url)
        resp = get_with_retries(self.client, url, sleep=self.sleep)
        self.pages += 1
        if resp.status_code != 200:
            log.warning("%s: HTTP %s, skipped", url, resp.status_code)
            return None
        log.info("[%d/%d] %s", self.pages, self.max_pages, url)
        return resp.content.decode("utf-8", errors="replace")

    def _resolve_category(self, html: str, start: str, category: str) -> str | None:
        links = parse_category_links(html, start)
        return links.get(category.lower())

    def crawl(self, start: str, category: str | None = None) -> Iterator[Book]:
        url: str | None = start
        if category:
            html = self._get(start)
            if html is None:
                return
            url = self._resolve_category(html, start, category)
            if url is None:
                log.error("category %r not found on %s", category, start)
                return
        while url and self.pages < self.max_pages:
            html = self._get(url)
            if html is None:
                break
            products, url = parse_listing(html, url)
            for product_url in products:
                page = self._get(product_url)
                if page is None:
                    if self.pages >= self.max_pages:
                        return
                    continue
                yield parse_product(page, product_url)


class _Throttled:
    """Wraps a client so robots.txt fetches also respect the host pause."""

    def __init__(self, client: httpx.Client, limiter: HostLimiter):
        self._client = client
        self._limiter = limiter

    def get(self, url: str) -> httpx.Response:
        self._limiter.wait(url)
        return self._client.get(url)
