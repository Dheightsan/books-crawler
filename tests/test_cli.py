import csv

import httpx

from crawler.__main__ import main

FIRST_PRODUCT = "/catalogue/a-light-in-the-attic_1000/index.html"


def make_transport(listing_html, product_html, overrides=None):
    """overrides maps a path to a callable(request) returning a response or raising."""
    overrides = overrides or {}

    def handler(req):
        path = req.url.path
        if path in overrides:
            return overrides[path](req)
        if path == "/robots.txt":
            return httpx.Response(404)
        if path == "/index.html":
            return httpx.Response(200, content=listing_html.encode("utf-8"))
        if path.startswith("/catalogue/") and path.endswith("/index.html"):
            # distinct UPC per product so the CSV has distinct rows
            html = product_html.replace("a897fe39b1053632", f"upc{abs(hash(path)) % 10**8}")
            return httpx.Response(200, content=html.encode("utf-8"))
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_short_run(tmp_path, listing_html, product_html):
    out = tmp_path / "books.csv"
    sleeps = []
    code = main(
        ["--start", "https://books.toscrape.com/index.html", "--max-pages", "4",
         "--delay", "1.0", "--out", str(out)],
        transport=make_transport(listing_html, product_html),
        sleep=sleeps.append,
    )
    assert code == 0
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3  # 1 listing + 3 products = 4 pages
    assert rows[0]["currency"] == "GBP"
    assert rows[0]["rating"] == "3"
    assert sleeps  # the host pause was applied


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_cli(tmp_path, transport, max_pages=4):
    out = tmp_path / "books.csv"
    code = main(
        ["--start", "https://books.toscrape.com/index.html", "--max-pages", str(max_pages),
         "--delay", "1.0", "--out", str(out)],
        transport=transport,
        sleep=lambda seconds: None,
    )
    return code, read_rows(out)


def test_malformed_product_is_skipped_and_others_written(
    tmp_path, listing_html, product_html, caplog
):
    def broken(req):
        return httpx.Response(200, content=b"<html><body>no book here</body></html>")

    transport = make_transport(listing_html, product_html, {FIRST_PRODUCT: broken})
    with caplog.at_level("INFO"):
        code, rows = run_cli(tmp_path, transport)
    assert code == 0
    assert len(rows) == 2  # 3 products requested, the first one is malformed
    assert "run summary: 4 pages downloaded, skipped 0 by robots.txt, 0 by network error, " in (
        caplog.text
    )
    assert "1 by parse error" in caplog.text
    assert f"https://books.toscrape.com{FIRST_PRODUCT}" in caplog.text
    assert "could not parse product page" in caplog.text


def test_network_error_on_product_is_skipped_and_run_continues(
    tmp_path, listing_html, product_html, caplog
):
    def boom(req):
        raise httpx.ReadTimeout("timed out", request=req)

    transport = make_transport(listing_html, product_html, {FIRST_PRODUCT: boom})
    with caplog.at_level("INFO"):
        code, rows = run_cli(tmp_path, transport)
    assert code == 0
    assert len(rows) == 2
    assert "1 by network error" in caplog.text
    assert "2 books written" in caplog.text
    assert "network error after retries" in caplog.text
    assert f"https://books.toscrape.com{FIRST_PRODUCT}" in caplog.text


ROBOTS_BLOCK = "User-agent: *\nDisallow: /catalogue/\n"


def test_summary_counts_robots_skips(tmp_path, listing_html, product_html, caplog):
    transport = make_transport(
        listing_html,
        product_html,
        {"/robots.txt": lambda req: httpx.Response(200, text=ROBOTS_BLOCK)},
    )
    with caplog.at_level("INFO"):
        code, rows = run_cli(tmp_path, transport)
    assert code == 0
    assert len(rows) == 0
    assert "skipped 21 by robots.txt" in caplog.text
    assert "1 pages downloaded" in caplog.text
