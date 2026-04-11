"""Tests for FetchResult data model."""

from pathlib import Path
from libby.models.fetch_result import FetchResult


def test_fetch_result_success():
    """Test successful fetch result."""
    result = FetchResult(
        doi="10.1007/s11142-016-9368-9",
        success=True,
        source="unpaywall",
        pdf_url="https://example.com/paper.pdf",
        pdf_path=Path("/papers/cheng_2016/cheng_2016.pdf"),
        bib_path=Path("/papers/cheng_2016/cheng_2016.bib"),
        metadata={"title": "Test Paper"},
    )

    assert result.success is True
    assert result.source == "unpaywall"
    assert result.doi == "10.1007/s11142-016-9368-9"


def test_fetch_result_failure():
    """Test failed fetch result."""
    result = FetchResult(
        doi="10.1007/s11142-016-9368-9",
        success=False,
        source=None,
        pdf_url=None,
        error="No PDF found",
    )

    assert result.success is False
    assert result.error == "No PDF found"


def test_fetch_result_to_dict():
    """Test serialization to dictionary."""
    result = FetchResult(
        doi="10.1007/s11142-016-9368-9",
        success=True,
        source="unpaywall",
        pdf_url="https://example.com/paper.pdf",
        pdf_path=Path("/papers/test.pdf"),
        bib_path=Path("/papers/test.bib"),
    )

    d = result.to_dict()

    assert d["doi"] == "10.1007/s11142-016-9368-9"
    assert d["source"] == "unpaywall"
    assert d["pdf_path"] == str(Path("/papers/test.pdf"))
    assert d["bib_path"] == str(Path("/papers/test.bib"))
