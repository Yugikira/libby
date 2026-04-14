"""Tests for SearchResult model."""

from libby.models.search_result import SearchResult, SerpapiExtraInfo


def test_search_result_merge():
    """Test field merging - longer values and missing fields."""
    r1 = SearchResult(
        doi="10.1234/test",
        title="Test Paper",
        author=["Smith, John"],
        sources=["crossref"],
    )

    r2 = SearchResult(
        doi="10.1234/test",
        title="Test Paper: A Longer Title",
        journal="Nature",
        sources=["semantic_scholar"],
    )

    r1.merge_from(r2)

    assert r1.title == "Test Paper: A Longer Title"  # Longer title kept
    assert r1.journal == "Nature"  # Missing field filled
    assert "crossref" in r1.sources
    assert "semantic_scholar" in r1.sources


def test_search_result_to_dict():
    """Test serialization."""
    r = SearchResult(
        doi="10.1234/test",
        title="Test",
        year=2023,
        sources=["crossref"],
    )

    d = r.to_dict()

    assert d["doi"] == "10.1234/test"
    assert d["title"] == "Test"
    assert d["year"] == 2023
    assert d["sources"] == ["crossref"]


def test_serpapi_extra_info():
    """Test Serpapi extra info."""
    e = SerpapiExtraInfo(
        title="Test Paper Title",
        link="https://example.com",
        cited_by_count=42,
    )

    d = e.to_dict()

    assert d["title"] == "Test Paper Title"
    assert d["cited_by_count"] == 42