"""Reports over the SQLite file: python -m crawler.report --db books.db [--load books.csv]"""

import argparse
import sqlite3

from . import db

BY_CATEGORY = """
SELECT category, COUNT(*) AS books, ROUND(AVG(price_minor) / 100.0, 2) AS avg_price
FROM books
GROUP BY category
ORDER BY books DESC, category
"""

IN_CATEGORY = """
SELECT title, price_minor / 100.0 AS price, rating
FROM books
WHERE category = ?
ORDER BY price_minor, title
LIMIT ?
"""

CHEAP_AND_GOOD = """
SELECT title, category, price_minor / 100.0 AS price, rating
FROM books
WHERE rating >= ?
ORDER BY price_minor, title
LIMIT ?
"""

LOW_STOCK = """
SELECT title, category, stock
FROM books
WHERE stock <= ?
ORDER BY stock, title
LIMIT ?
"""


def by_category(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(BY_CATEGORY).fetchall()


def in_category(conn: sqlite3.Connection, category: str, limit: int = 5) -> list[tuple]:
    return conn.execute(IN_CATEGORY, (category, limit)).fetchall()


def cheap_and_good(conn: sqlite3.Connection, min_rating: int = 4, limit: int = 5) -> list[tuple]:
    return conn.execute(CHEAP_AND_GOOD, (min_rating, limit)).fetchall()


def low_stock(conn: sqlite3.Connection, max_stock: int = 5, limit: int = 10) -> list[tuple]:
    return conn.execute(LOW_STOCK, (max_stock, limit)).fetchall()


def _show(title: str, header: list[str], rows: list[tuple]) -> None:
    print(f"\n{title}")
    print(" | ".join(header))
    for row in rows:
        print(" | ".join(str(v) for v in row))
    if not rows:
        print("(no rows)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="crawler.report", description="Reports over the books DB")
    p.add_argument("--db", required=True, help="SQLite file")
    p.add_argument("--load", help="load this CSV into the DB first (no network)")
    p.add_argument("--category", default="Travel", help="category for the per-category list")
    args = p.parse_args(argv)
    conn = db.connect(args.db)
    try:
        if args.load:
            print(f"loaded {db.load_csv(conn, args.load)} books from {args.load}")
        _show("Books and average price (GBP) per category",
              ["category", "books", "avg_price"], by_category(conn))
        _show(f"Cheapest in {args.category}",
              ["title", "price", "rating"], in_category(conn, args.category))
        _show("Cheapest with rating 4 or more",
              ["title", "category", "price", "rating"], cheap_and_good(conn))
        _show("Low stock (5 or fewer)",
              ["title", "category", "stock"], low_stock(conn))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
