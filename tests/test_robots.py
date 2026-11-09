import httpx

from crawler.robots import RobotsCache

ROBOTS = "User-agent: *\nDisallow: /private/\n"


def make(handler, sleeps=None):
    sleeps = [] if sleeps is None else sleeps
    return RobotsCache(
        httpx.Client(transport=httpx.MockTransport(handler)), "test-bot/1.0", sleep=sleeps.append
    )


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


def test_5xx_means_disallow_all_after_retries():
    calls = []
    sleeps = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(503)

    cache = make(handler, sleeps)
    assert not cache.allowed("https://example.com/public/x.html")
    assert not cache.allowed("https://example.com/other.html")
    assert len(calls) == 5  # first try plus 4 retries, then cached for the run
    assert sleeps == [1.0, 2.0, 4.0, 8.0]


def test_429_means_disallow_all():
    cache = make(lambda req: httpx.Response(429, headers={"Retry-After": "2"}))
    assert not cache.allowed("https://example.com/public/x.html")


def test_network_error_means_disallow_all(caplog):
    def handler(req):
        raise httpx.ConnectError("boom", request=req)

    sleeps = []
    cache = make(handler, sleeps)
    with caplog.at_level("WARNING"):
        assert not cache.allowed("https://example.com/public/x.html")
    assert len(sleeps) == 4
    assert "robots.txt unreachable" in caplog.text
    assert "https://example.com" in caplog.text


def test_server_recovers_during_retries():
    replies = iter([httpx.Response(503), httpx.Response(200, text=ROBOTS)])
    cache = make(lambda req: next(replies))
    assert cache.allowed("https://example.com/public/x.html")
    assert not cache.allowed("https://example.com/private/x.html")


def test_other_4xx_means_allowed():
    for status in (401, 403, 410):
        cache = make(lambda req, status=status: httpx.Response(status))
        assert cache.allowed("https://example.com/private/x.html")


def test_failure_is_per_host():
    def handler(req):
        if req.url.host == "down.test":
            return httpx.Response(500)
        return httpx.Response(404)

    cache = make(handler)
    assert not cache.allowed("https://down.test/a")
    assert cache.allowed("https://up.test/a")
