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
- `--db books.db` also save the books to SQLite (see below)

## Example

`examples/sample.csv` comes from one real run (Travel category plus the first
books of the front page, 25 pages fetched, 23 unique books):

```
python -m crawler --start https://books.toscrape.com/catalogue/category/books/travel_2/index.html --start https://books.toscrape.com/index.html --max-pages 25 --delay 1.0 --out examples/sample.csv
```

## Docker

The image has only the runtime dependencies and runs as a non-root user. It works
in `/data`, so mount the folder where you want the files:

```
docker build -t books-crawler .
docker run --rm -v "$PWD:/data" --user "$(id -u):$(id -g)" books-crawler --start https://books.toscrape.com/ --max-pages 25 --out books.csv --db books.db
docker run --rm -v "$PWD:/data" --user "$(id -u):$(id -g)" --entrypoint python books-crawler -m crawler.report --db books.db
```

`--user` keeps the output files owned by you on Linux; Docker Desktop doesn't
need it. CI builds the image on every push and runs the reports inside it on
`examples/sample.csv`, with no network.

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

## SQLite

`--db books.db` saves the same books to SQLite as well as the CSV. It uses only the
standard library (`sqlite3`). Run it twice and the second run updates the rows
instead of adding them again.

```
.venv/Scripts/python -m crawler --start https://books.toscrape.com/ --out books.csv --db books.db
```

Schema (`PRAGMA user_version = 1`):

```sql
CREATE TABLE books (
    upc         TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
    currency    TEXT NOT NULL,
    stock       INTEGER NOT NULL CHECK (stock >= 0),
    rating      INTEGER CHECK (rating BETWEEN 1 AND 5),
    category    TEXT NOT NULL,
    url         TEXT NOT NULL,
    crawled_at  TEXT NOT NULL
);
CREATE INDEX idx_books_category ON books (category);
```

- The price is an integer in pence (`4517` is 45.17), because float sums and averages
  are not exact. The reports divide by 100.
- A page with no stars gets `rating = NULL`, so the 1 to 5 check never blocks a run.
- All writes of a run are one transaction: if one row fails, none is saved.
- `INSERT ... ON CONFLICT (upc) DO UPDATE` is the upsert. Queries take their values as
  `?` parameters, never by pasting text into the SQL.

### Index

There is one index, `idx_books_category`. Two queries use it: the per-category
`GROUP BY` and `WHERE category = ?`. A test checks with `EXPLAIN QUERY PLAN` that
SQLite picks it. The "cheap with good rating" and "low stock" queries scan the whole
table, which is fine for a few thousand rows. An index for them would be added
only after measuring.

### Reports

`crawler/report.py` loads a CSV without network and runs four queries (the SQL is at
the top of the file):

1. books and average price per category (`GROUP BY`, `ORDER BY`)
2. cheapest books of one category (`WHERE category = ?`, `LIMIT`)
3. cheapest books with rating 4 or more
4. books with 5 or fewer units in stock

```
.venv/Scripts/python -m crawler.report --db sample.db --load examples/sample.csv
```

Output on `examples/sample.csv`:

```
loaded 23 books from examples/sample.csv

Books and average price (GBP) per category
category | books | avg_price
Travel | 11 | 39.79
Default | 3 | 18.17
Poetry | 3 | 41.53
Business | 1 | 33.34
Fiction | 1 | 50.1
Historical Fiction | 1 | 53.74
History | 1 | 54.23
Mystery | 1 | 47.82
Young Adult | 1 | 22.65

Cheapest in Travel
title | price | rating
The Road to Little Dribbling: Adventures of an American in Britain (Notes From a Small Island #2) | 23.21 | 1
1,000 Places to See Before You Die | 26.08 | 5
The Great Railway Bazaar | 30.54 | 1
Vagabonding: An Uncommon Guide to the Art of Long-Term World Travel | 36.94 | 2
Under the Tuscan Sun | 37.33 | 3

Cheapest with rating 4 or more
title | category | price | rating
Shakespeare's Sonnets | Poetry | 20.66 | 4
The Boys in the Boat: Nine Americans and Their Epic Quest for Gold at the 1936 Berlin Olympics | Default | 22.6 | 4
1,000 Places to See Before You Die | Travel | 26.08 | 5
The Dirty Little Secrets of Getting Your Dream Job | Business | 33.34 | 4
Sharp Objects | Mystery | 47.82 | 4

Low stock (5 or fewer)
title | category | stock
1,000 Places to See Before You Die | Travel | 1
Neither Here nor There: Travels in Europe | Travel | 3
The Road to Little Dribbling: Adventures of an American in Britain (Notes From a Small Island #2) | Travel | 3
```

## Politeness

- Reads `robots.txt` once per host and skips disallowed URLs (logged), following
  RFC 9309. A 2xx response is parsed. Any other 4xx except 429 (404, 403 and so on)
  means everything is allowed. A 5xx, a 429 or a network error is retried with
  backoff, and if it still fails (or the answer is anything else, such as a redirect
  that cannot be followed) the whole host is treated as disallowed for the rest of
  the run, with a warning.
- Waits at least `--delay` seconds between requests to the same host, robots.txt
  included.
- Sends a User-Agent that names the project and where to find it.
- Retries 429, 5xx and network errors with exponential backoff, and honors
  `Retry-After`. Gives up after 4 retries.
- A page that still fails after the retries is logged with its URL and the cause,
  counts toward `--max-pages`, and the run goes on with the next URL. A product page
  that cannot be parsed is logged and skipped the same way.
- At the end of a run it logs one summary line with the pages downloaded, the pages
  skipped by robots.txt, network error, parse error and HTTP status, and the books
  written.

## How it works

`crawler/fetch.py` is the HTTP client, `robots.py` and `ratelimit.py` hold the
rules, `parse.py` turns HTML into `Book` objects (selectolax), `export.py` writes
the CSV with fixed columns and one row per UPC, `db.py` and `report.py` handle the
SQLite file, and `crawl.py` ties them together.

## Tests

```
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest -q
```

The tests never touch the network. Parsing runs on saved pages in
`tests/fixtures/`, and the CLI test uses `httpx.MockTransport`.

## License

MIT, see `LICENSE`.
