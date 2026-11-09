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

- Reads `robots.txt` once per host and skips disallowed URLs (logged), following
  RFC 9309. A 2xx response is parsed. Any other 4xx except 429 (404, 403 and so on)
  means everything is allowed. A 5xx, a 429 or a network error is retried with
  backoff, and if it still fails the whole host is treated as disallowed for the
  rest of the run, with a warning.
- Waits at least `--delay` seconds between requests to the same host, robots.txt
  included.
- Sends a User-Agent that names the project and where to find it.
- Retries 429, 5xx and network errors with exponential backoff, and honors
  `Retry-After`. Gives up after 4 retries.
- A page that still fails after the retries is logged with its URL and the cause,
  counts toward `--max-pages`, and the run goes on with the next URL. A product page
  that cannot be parsed is logged and skipped the same way.

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
