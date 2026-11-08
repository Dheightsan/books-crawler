import httpx

from crawler.robots import RobotsCache

ROBOTS = "User-agent: *\nDisallow: /private/\n"


def make(handler):
    return RobotsCache(httpx.Client(transport=httpx.MockTransport(handler)), "test-bot/1.0")


def test_disallowed_and_allowed():
    cache = make(lambda req: httpx.Response(200, text=ROBOTS))
    assert not cache.allowed("https://example.com/private/x.html")
    assert cache.allowed("https://example.com/public/x.html")


def test_404_means_allowed():
    cache = make(lambda req: httpx.Response(404))
    assert cache.allowed("https://example.com/private/x.html")


def test_cached_per_host():
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(200, text=ROBOTS)

    cache = make(handler)
    cache.allowed("https://example.com/a")
    cache.allowed("https://example.com/b")
    cache.allowed("https://other.org/a")
    assert calls == ["https://example.com/robots.txt", "https://other.org/robots.txt"]
