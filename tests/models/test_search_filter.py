"""Tests for SearchFilter model."""

from libby.models.search_filter import SearchFilter
from datetime import datetime


def test_search_filter_defaults():
    """Test default year_from is 2 years ago."""
    filter = SearchFilter()

    expected_year = datetime.now().year - 2
    assert filter.year_from == expected_year
    assert filter.year_to is None
    assert filter.venue is None
    assert filter.issn is None


def test_search_filter_custom():
    """Test custom filter values."""
    filter = SearchFilter(
        year_from=2020,
        year_to=2024,
        venue="Nature",
        issn="0028-0836",
    )

    assert filter.year_from == 2020
    assert filter.year_to == 2024
    assert filter.venue == "Nature"
    assert filter.issn == "0028-0836"


def test_search_filter_native_params():
    """Test native params passthrough."""
    filter = SearchFilter(native_params={"has-funder": "true"})

    assert filter.native_params["has-funder"] == "true"