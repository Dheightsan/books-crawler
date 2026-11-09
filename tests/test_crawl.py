import httpx

from crawler.crawl import Crawler


def run(handler, start="https://books.toscrape.com/index.html", max_pages=10):
    sleeps = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    crawler = Crawler(client, delay=1.0, max_pages=max_pages, sleep=sleeps.append)
    books = list(crawler.crawl(start))
    return crawler, books, sleeps


def test_robots_503_downloads_nothing_from_host():
    seen = []

    def handler(req):
        seen.append(req.url.path)
        return httpx.Response(503)

    crawler, books, _ = run(handler)
    assert books == []
    assert set(seen) == {"/robots.txt"}
    assert crawler.pages == 0


def test_robots_network_error_downloads_nothing_from_host():
    seen = []

    def handler(req):
        seen.append(req.url.path)
        raise httpx.ConnectTimeout("timeout", request=req)

    crawler, books, _ = run(handler)
    assert books == []
    assert set(seen) == {"/robots.txt"}
    assert crawler.pages == 0


def test_robots_429_downloads_nothing_from_host():
    seen = []

    def handler(req):
        seen.append(req.url.path)
        return httpx.Response(429)

    crawler, books, _ = run(handler)
    assert books == []
    assert set(seen) == {"/robots.txt"}
    assert crawler.pages == 0


def test_robots_404_allows_everything(listing_html):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=listing_html.encode("utf-8"))

    crawler, _, _ = run(handler, max_pages=1)
    assert crawler.pages == 1


def test_failed_pages_count_toward_the_budget(listing_html, product_html):
    def handler(req):
        path = req.url.path
        if path == "/robots.txt":
            return httpx.Response(404)
        if path == "/index.html":
            return httpx.Response(200, content=listing_html.encode("utf-8"))
        if path == "/catalogue/a-light-in-the-attic_1000/index.html":
            raise httpx.ConnectError("refused", request=req)
        return httpx.Response(200, content=product_html.encode("utf-8"))

    crawler, books, sleeps = run(handler, max_pages=3)
    assert crawler.pages == 3  # listing, failed product, one good product
    assert len(books) == 1
    assert len(sleeps) >= 4  # the failed product was retried with backoff
