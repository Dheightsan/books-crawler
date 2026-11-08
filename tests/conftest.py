from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def listing_html() -> str:
    return (FIXTURES / "listing.html").read_text(encoding="utf-8")


@pytest.fixture
def product_html() -> str:
    return (FIXTURES / "product.html").read_text(encoding="utf-8")
