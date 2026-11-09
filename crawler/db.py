"""SQLite storage: schema, upsert by UPC and CSV loading. Standard library only."""

import csv
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime

from .parse import Book

SCHEMA_VERSION = 1

# Price is stored as an integer in the currency's minor unit (pence). A REAL like
# 45.17 is a binary float, so sums and averages pick up tiny errors. An integer is
# exact and we divide by 100 only when we print.
SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
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
-- Serves "books of one category" (WHERE category = ?) and the per-category GROUP BY.
CREATE INDEX IF NOT EXISTS idx_books_category ON books (category);
"""

UPSERT = """
INSERT INTO books (upc, title, price_minor, currency, stock, rating, category, url, crawled_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (upc) DO UPDATE SET
    title = excluded.title,
    price_minor = excluded.price_minor,
    currency = excluded.currency,
    stock = excluded.stock,
    rating = excluded.rating,
    category = excluded.category,
    url = excluded.url,
    crawled_at = excluded.crawled_at
"""


def connect(path: str) -> sqlite3.Connection:
    """Open the database and create the schema on first use."""
    conn = sqlite3.connect(path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(f"{path} has schema version {version}, newer than {SCHEMA_VERSION}")
    if version == 0:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


def save_books(
    conn: sqlite3.Connection, books: Iterable[Book], crawled_at: str | None = None
) -> int:
    """Upsert books by UPC in one transaction. Returns the number of distinct UPCs written."""
    stamp = crawled_at or datetime.now(UTC).isoformat(timespec="seconds")
    first = {}  # same rule as the CSV: if a UPC repeats, the first one wins
    for b in books:
        first.setdefault(b.upc, b)
    rows = [
        (
            b.upc, b.title, round(b.price * 100), b.currency, b.stock,
            b.rating or None,  # the parser uses 0 for "no stars found"; store NULL
            b.category, b.url, stamp,
        )
        for b in first.values()
    ]
    with conn:  # commit on success, roll back everything if one row fails
        conn.executemany(UPSERT, rows)
    return len(rows)


def load_csv(conn: sqlite3.Connection, path: str, crawled_at: str | None = None) -> int:
    """Load a CSV written by this crawler (e.g. examples/sample.csv), no network."""
    with open(path, newline="", encoding="utf-8") as fh:
        books = [
            Book(
                r["title"], float(r["price"]), r["currency"], int(r["stock"]),
                int(r["rating"]), r["upc"], r["category"], r["url"],
            )
            for r in csv.DictReader(fh)
        ]
    return save_books(conn, books, crawled_at)
