import csv

import httpx

from crawler.__main__ import main


def make_transport(listing_html, product_html):
    def handler(req):
        path = req.url.path
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
