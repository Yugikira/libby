"""Tests for metadata models."""

import pytest

from libby.models.metadata import BibTeXMetadata
from libby.models.result import BatchResult


def test_bibtex_metadata_creation():
    """Test creating BibTeX metadata."""
    metadata = BibTeXMetadata(
        citekey="stent_2016_earnings",
        entry_type="article",
        author=["Stent, Angela", "Yang, Kaitlin"],
        title="Earnings Management Consequences",
        year=2016,
        doi="10.1007/s11142-016-9368-9",
    )
    assert metadata.citekey == "stent_2016_earnings"
    assert len(metadata.author) == 2
    assert metadata.year == 2016


def test_bibtex_metadata_to_dict():
    """Test converting to dictionary."""
    metadata = BibTeXMetadata(
        citekey="test_2024_paper",
        title="Test Paper",
        year=2024,
    )
    d = metadata.to_dict()
    assert d["citekey"] == "test_2024_paper"
    assert d["title"] == "Test Paper"
    assert d["year"] == 2024


def test_batch_result():
    """Test batch result calculation."""
    result = BatchResult(
        succeeded=[{"a": 1}, {"b": 2}],
        failed=[{"c": 3}],
    )
    assert result.total == 3
    assert result.success_rate == pytest.approx(66.67, rel=0.01)