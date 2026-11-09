import pytest

from crawler.parse import ParseError, parse_category_links, parse_listing, parse_product

BASE = "https://books.toscrape.com/index.html"


def test_listing_links_and_next(listing_html):
    products, nxt = parse_listing(listing_html, BASE)
    assert len(products) == 20
    assert products[0] == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert nxt == "https://books.toscrape.com/catalogue/page-2.html"


def test_category_links(listing_html):
    links = parse_category_links(listing_html, BASE)
    assert links["travel"].endswith("/catalogue/category/books/travel_2/index.html")


def test_product_fields(product_html):
    url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    book = parse_product(product_html, url)
    assert book.title == "A Light in the Attic"
    assert book.price == 51.77
    assert book.currency == "GBP"
    assert book.stock == 22
    assert book.rating == 3
    assert book.upc == "a897fe39b1053632"
    assert book.category == "Poetry"
    assert book.url == url


def test_missing_title_raises_parse_error():
    with pytest.raises(ParseError, match="missing element"):
        parse_product("<html><body></body></html>", "https://x.test/p")


def test_unreadable_price_raises_parse_error(product_html):
    broken = product_html.replace("£51.77", "free")
    with pytest.raises(ParseError, match="unreadable price"):
        parse_product(broken, "https://x.test/p")
