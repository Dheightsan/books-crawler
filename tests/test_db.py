import sqlite3
from pathlib import Path

import pytest

from crawler import db, report
from crawler.parse import Book

SAMPLE = Path(__file__).parent.parent / "examples" / "sample.csv"


def book(upc, title="T", price=10.5, stock=3, rating=4, category="Travel"):
    return Book(title, price, "GBP", stock, rating, upc, category, f"https://x.test/{upc}")


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


def test_schema_created(conn):
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    cols = [r[1] for r in conn.execute("PRAGMA table_info(books)")]
    assert cols == ["upc", "title", "price_minor", "currency", "stock",
                    "rating", "category", "url", "crawled_at"]


def test_second_run_updates_instead_of_duplicating(conn):
    db.save_books(conn, [book("a"), book("b")], "2026-11-01T00:00:00")
    db.save_books(conn, [book("a", title="New", price=9.99)], "2026-11-02T00:00:00")
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 2
    row = conn.execute(
        "SELECT title, price_minor, crawled_at FROM books WHERE upc = 'a'"
    ).fetchone()
    assert row == ("New", 999, "2026-11-02T00:00:00")


def test_repeated_upc_in_one_batch_keeps_the_first(conn):
    n = db.save_books(conn, [book("a", title="First"), book("a", title="Second")])
    assert n == 1
    assert conn.execute("SELECT title FROM books WHERE upc = 'a'").fetchone()[0] == "First"


def test_rating_check_rejects_out_of_range(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.save_books(conn, [book("a", rating=6)])


def test_failed_run_rolls_back_everything(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.save_books(conn, [book("a"), book("b", rating=9)])
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0


def test_missing_rating_is_stored_as_null(conn):
    db.save_books(conn, [book("a", rating=0)])
    assert conn.execute("SELECT rating FROM books").fetchone()[0] is None


def test_newer_schema_is_refused(tmp_path):
    path = str(tmp_path / "x.db")
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    with pytest.raises(RuntimeError):
        db.connect(path)


@pytest.fixture
def sample(conn):
    assert db.load_csv(conn, str(SAMPLE)) == 23
    return conn


def test_by_category(sample):
    rows = report.by_category(sample)
    assert rows[0] == ("Travel", 11, 39.79)
    assert sum(r[1] for r in rows) == 23


def test_in_category_is_sorted_and_limited(sample):
    rows = report.in_category(sample, "Travel", limit=2)
    assert [r[1] for r in rows] == [23.21, 26.08]


def test_in_category_takes_text_as_a_value(sample):
    assert report.in_category(sample, "Travel' OR '1'='1") == []


def test_cheap_and_good(sample):
    rows = report.cheap_and_good(sample, min_rating=4, limit=3)
    assert [r[0] for r in rows][0] == "Shakespeare's Sonnets"
    assert all(r[3] >= 4 for r in rows)
    assert [r[2] for r in rows] == sorted(r[2] for r in rows)


def test_low_stock(sample):
    rows = report.low_stock(sample, max_stock=3)
    assert [r[2] for r in rows] == [1, 3, 3]


def plan(conn, sql, params):
    return " ".join(str(r[3]) for r in conn.execute("EXPLAIN QUERY PLAN " + sql, params))


def test_category_query_uses_the_index(sample):
    text = plan(sample, report.IN_CATEGORY, ("Travel", 5))
    assert "idx_books_category" in text


def test_group_by_category_uses_the_index(sample):
    assert "idx_books_category" in plan(sample, report.BY_CATEGORY, ())
