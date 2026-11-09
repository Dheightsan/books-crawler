"""Command line entry point: python -m crawler --start URL --out books.csv"""

import argparse
import logging
import sys
import time

import httpx

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

    def books():
        for start in args.start:
            yield from crawler.crawl(start, args.category)

    try:
        rows = write_csv(books(), args.out)
    finally:
        client.close()
    logging.info("wrote %d books to %s", rows, args.out)
    logging.info("run summary: %s", crawler.stats.summary(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
