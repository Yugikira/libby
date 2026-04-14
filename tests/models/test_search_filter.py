"""Tests for SearchFilter model."""

from libby.models.search_filter import SearchFilter
from datetime import datetime


def test_search_filter_defaults():
    """Test default filter has no auto-set year_from.

    Note: year_from default is set by caller (CLI/API), not by SearchFilter itself.
    This allows extract to work without year restrictions while websearch applies default.
    """
    filter = SearchFilter()

    # SearchFilter does NOT auto-set year_from - caller decides
    assert filter.year_from is None
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