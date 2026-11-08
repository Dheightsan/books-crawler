import csv

from crawler.export import COLUMNS, write_csv
from crawler.parse import Book


def book(upc, title="T"):
    return Book(title, 10.5, "GBP", 3, 4, upc, "Travel", f"https://x.test/{upc}")


def test_dedupes_by_upc(tmp_path):
    out = tmp_path / "b.csv"
    n = write_csv([book("a"), book("b"), book("a", "Again")], str(out))
    assert n == 2
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["upc"] for r in rows] == ["a", "b"]
    assert rows[0]["title"] == "T"


def test_fixed_columns(tmp_path):
    out = tmp_path / "b.csv"
    write_csv([book("a")], str(out))
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == COLUMNS
