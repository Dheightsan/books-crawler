"""CSV export with fixed columns, one row per UPC."""

import csv
from collections.abc import Iterable
from dataclasses import asdict

from .parse import Book

COLUMNS = ["title", "price", "currency", "stock", "rating", "upc", "category", "url"]


def write_csv(books: Iterable[Book], path: str) -> int:
    """Write books to path, skipping repeated UPCs. Returns rows written."""
    seen: set[str] = set()
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for book in books:
            if book.upc in seen:
                continue
            seen.add(book.upc)
            writer.writerow(asdict(book))
            count += 1
    return count
