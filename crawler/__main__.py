"""Command line entry point: python -m crawler --start URL --out books.csv"""

import argparse
import logging
import sys
import time

import httpx

from . import db
from .crawl import Crawler
from .export import write_csv
from .fetch import make_client


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crawler", description="Polite books.toscrape.com crawler")
    p.add_argument("--start", action="append", required=True, help="start URL (repeatable)")
    p.add_argument("--max-pages", type=int, default=25, help="page budget, listings included")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between requests per host")
    p.add_argument("--out", default="books.csv", help="CSV output path")
    p.add_argument("--category", help="only crawl this category, e.g. travel")
    p.add_argument("--db", help="also save the books to this SQLite file (upsert by UPC)")
    return p


def main(
    argv: list[str] | None = None,
    transport: httpx.BaseTransport | None = None,
    sleep=time.sleep,
) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = make_client(transport)
    crawler = Crawler(client, delay=args.delay, max_pages=args.max_pages, sleep=sleep)

    collected = []

    def books():
        for start in args.start:
            for book in crawler.crawl(start, args.category):
                collected.append(book)
                yield book

    try:
        rows = write_csv(books(), args.out)
    finally:
        client.close()
    logging.info("wrote %d books to %s", rows, args.out)
    if args.db:
        conn = db.connect(args.db)
        try:
            logging.info("saved %d books to %s", db.save_books(conn, collected), args.db)
        finally:
            conn.close()
    logging.info("run summary: %s", crawler.stats.summary(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
