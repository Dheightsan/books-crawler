import httpx

from crawler import USER_AGENT
from crawler.fetch import get_with_retries, retry_after_seconds


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT})


def test_backoff_on_5xx():
    codes = iter([503, 500, 200])
    sleeps = []
    c = client(lambda req: httpx.Response(next(codes)))
    resp = get_with_retries(c, "https://x.test/", base_delay=1.0, sleep=sleeps.append)
    assert resp.status_code == 200
    assert sleeps == [1.0, 2.0]


def test_retry_after_wins():
    replies = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)])
    sleeps = []
    c = client(lambda req: next(replies))
    get_with_retries(c, "https://x.test/", sleep=sleeps.append)
    assert sleeps == [7.0]


def test_gives_up_after_retries():
    sleeps = []
    c = client(lambda req: httpx.Response(503))
    resp = get_with_retries(c, "https://x.test/", retries=2, sleep=sleeps.append)
    assert resp.status_code == 503
    assert len(sleeps) == 2


def test_404_not_retried():
    sleeps = []
    c = client(lambda req: httpx.Response(404))
    assert get_with_retries(c, "https://x.test/", sleep=sleeps.append).status_code == 404
    assert sleeps == []


def test_user_agent_sent():
    seen = []

    def handler(req):
        seen.append(req.headers["User-Agent"])
        return httpx.Response(200)

    get_with_retries(client(handler), "https://x.test/")
    assert seen == [USER_AGENT]
    assert "github.com/Dheightsan/books-crawler" in USER_AGENT


def test_retry_after_parsing():
    assert retry_after_seconds("3") == 3.0
    assert retry_after_seconds(None) is None
    assert retry_after_seconds("nonsense") is None
