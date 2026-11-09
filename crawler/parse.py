"""HTML parsing for listing and product pages."""

from dataclasses import dataclass
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
CURRENCIES = {"£": "GBP", "$": "USD", "€": "EUR"}


class ParseError(ValueError):
    """A product page lacks a required element or holds a value that cannot be read."""


@dataclass
class Book:
    title: str
    price: float
    currency: str
    stock: int
    rating: int
    upc: str
    category: str
    url: str


def parse_listing(html: str, base_url: str) -> tuple[list[str], str | None]:
    """Return product links and the next page URL (None on the last page)."""
    tree = HTMLParser(html)
    products = []
    for a in tree.css("article.product_pod h3 a"):
        href = a.attributes.get("href")
        if href:
            products.append(urljoin(base_url, href))
    nxt = tree.css_first("li.next a")
    next_href = nxt.attributes.get("href") if nxt else None
    next_url = urljoin(base_url, next_href) if next_href else None
    return products, next_url


def parse_category_links(html: str, base_url: str) -> dict[str, str]:
    """Map lowercase category name to its listing URL, from the sidebar."""
    tree = HTMLParser(html)
    out = {}
    for a in tree.css("div.side_categories ul ul li a"):
        href = a.attributes.get("href")
        if href:
            out[a.text(strip=True).lower()] = urljoin(base_url, href)
    return out


def _parse_price(text: str) -> tuple[float, str]:
    text = text.strip()
    try:
        return float(text[1:]), CURRENCIES.get(text[0], text[0])
    except (ValueError, IndexError) as exc:
        raise ParseError(f"unreadable price {text!r}") from exc


def _required(tree: HTMLParser, selector: str):
    node = tree.css_first(selector)
    if node is None:
        raise ParseError(f"missing element {selector!r}")
    return node


def _parse_stock(text: str) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def parse_product(html: str, url: str) -> Book:
    """Parse a product page. Raises ParseError when title, price or stock is unusable."""
    tree = HTMLParser(html)
    title = _required(tree, "div.product_main h1").text(strip=True)
    price, currency = _parse_price(_required(tree, "div.product_main p.price_color").text())
    stock = _parse_stock(_required(tree, "div.product_main p.availability").text())

    rating = 0
    star = tree.css_first("div.product_main p.star-rating")
    if star:
        for cls in star.attributes.get("class", "").split():
            rating = RATINGS.get(cls, rating)

    table = {}
    for row in tree.css("table.table-striped tr"):
        th, td = row.css_first("th"), row.css_first("td")
        if th and td:
            table[th.text(strip=True)] = td.text(strip=True)

    crumbs = tree.css("ul.breadcrumb li")
    category = crumbs[2].text(strip=True) if len(crumbs) > 2 else ""

    return Book(
        title=title,
        price=price,
        currency=currency,
        stock=stock,
        rating=rating,
        upc=table.get("UPC", ""),
        category=category,
        url=url,
    )
