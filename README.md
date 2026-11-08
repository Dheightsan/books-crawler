# books-crawler

A small, polite crawler for [books.toscrape.com](https://books.toscrape.com/), a
practice site built for scraping. It walks listing pages, opens each book page and
writes the result to a CSV file.

## Quick start

Python 3.12 or newer.

```
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"    # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m crawler --start https://books.toscrape.com/ --max-pages 25 --out books.csv
```

Options:

- `--start URL` start page, can be repeated
- `--max-pages N` page budget, listing pages included (default 25)
- `--delay 1.0` minimum seconds between requests to the same host
- `--out books.csv` output file
- `--category travel` follow only one category from the start page

## Example

`examples/sample.csv` comes from one real run (Travel category plus the first
books of the front page, 25 pages fetched, 23 unique books):

```
python -m crawler --start https://books.toscrape.com/catalogue/category/books/travel_2/index.html --start https://books.toscrape.com/index.html --max-pages 25 --delay 1.0 --out examples/sample.csv
```

## CSV columns

| column | meaning |
| --- | --- |
| title | book title |
| price | price as a number |
| currency | ISO code, `GBP` for the site's pound sign |
| stock | units available |
| rating | stars, 1 to 5 |
| upc | product code, used to drop duplicates |
| category | category from the breadcrumb |
| url | product page |

## Politeness

- Reads `robots.txt` once per host and skips disallowed URLs (logged). A 404 means
  everything is allowed.
- Waits at least `--delay` seconds between requests to the same host, robots.txt
  included.
- Sends a User-Agent that names the project and where to find it.
- Retries 429 and 5xx responses with exponential backoff, and honors `Retry-After`.
  Gives up after 4 retries.

## How it works

`crawler/fetch.py` is the HTTP client, `robots.py` and `ratelimit.py` hold the
rules, `parse.py` turns HTML into `Book` objects (selectolax), `export.py` writes
the CSV with fixed columns and one row per UPC, and `crawl.py` ties them together.

## Tests

```
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest -q
```

The tests never touch the network. Parsing runs on saved pages in
`tests/fixtures/`, and the CLI test uses `httpx.MockTransport`.

## License

MIT, see `LICENSE`.
