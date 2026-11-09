"""Crawl loop: listing pages, then product pages, within a page budget."""

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import httpx

from . import USER_AGENT
from .fetch import get_with_retries
from .parse import Book, ParseError, parse_category_links, parse_listing, parse_product
from .ratelimit import HostLimiter
from .robots import RobotsCache

log = logging.getLogger(__name__)


@dataclass
class CrawlStats:
    """Outcome counters for one run. A URL not downloaded lands in one skip bucket.

    skipped_parse counts pages that were downloaded but could not be parsed.
    """

    downloaded: int = 0
    skipped_robots: int = 0
    skipped_network: int = 0
    skipped_parse: int = 0
    skipped_http: int = 0  # answered, but not with 200

    def summary(self, books_written: int) -> str:
        return (
            f"{self.downloaded} pages downloaded, "
            f"skipped {self.skipped_robots} by robots.txt, "
            f"{self.skipped_network} by network error, "
            f"{self.skipped_parse} by parse error, {self.skipped_http} by HTTP status; "
            f"{books_written} books written"
        )


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
        self.stats = CrawlStats()

    def _get(self, url: str) -> str | None:
        """Fetch one page if robots.txt, the budget and the status allow it."""
        if url in self.seen or self.pages >= self.max_pages:
            return None
        if not self.robots.allowed(url):
            self.stats.skipped_robots += 1
            return None
        self.seen.add(url)
        self.limiter.wait(url)
        try:
            resp = get_with_retries(self.client, url, sleep=self.sleep)
        except httpx.RequestError as exc:
            self.pages += 1
            self.stats.skipped_network += 1
            log.warning(
                "%s: network error after retries (%s: %s), skipped",
                url, type(exc).__name__, exc,
            )
            return None
        self.pages += 1
        if resp.status_code != 200:
            self.stats.skipped_http += 1
            log.warning("%s: HTTP %s, skipped", url, resp.status_code)
            return None
        self.stats.downloaded += 1
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
                try:
                    book = parse_product(page, product_url)
                except ParseError as exc:
                    self.stats.skipped_parse += 1
                    log.warning("%s: could not parse product page (%s), skipped", product_url, exc)
                    continue
                yield book


class _Throttled:
    """Wraps a client so robots.txt fetches also respect the host pause."""

    def __init__(self, client: httpx.Client, limiter: HostLimiter):
        self._client = client
        self._limiter = limiter

    def get(self, url: str) -> httpx.Response:
        self._limiter.wait(url)
        return self._client.get(url)
