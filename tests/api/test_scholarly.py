"""Tests for Scholarly API (Google Scholar wrapper)."""

import pytest
from unittest.mock import patch, MagicMock
from libby.api.scholarly import ScholarlyAPI
from libby.models.search_filter import SearchFilter


@pytest.mark.asyncio
async def test_search_basic():
    """Test basic search returns results."""
    api = ScholarlyAPI()

    mock_results = [
        {"title": "Paper 1", "year": 2023, "url": "https://example.com/1"},
        {"title": "Paper 2", "year": 2024, "url": "https://example.com/2"},
    ]

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)

        results = await api.search("machine learning", limit=10)

        assert len(results) == 2
        assert results[0]["title"] == "Paper 1"

    await api.close()


@pytest.mark.asyncio
async def test_search_with_year_filter():
    """Test year filter adds keywords to query."""
    api = ScholarlyAPI()

    mock_results = [
        {"title": "Recent Paper", "year": 2023},
    ]

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)

        filter_obj = SearchFilter(year_from=2020, year_to=2024)
        results = await api.search("deep learning", limit=10, filter=filter_obj)

        # Verify the enhanced query includes year filters
        call_args = mock_search.call_args.args
        enhanced_query = call_args[0]
        assert "after:2020" in enhanced_query
        assert "before:2024" in enhanced_query

    await api.close()


@pytest.mark.asyncio
async def test_search_with_venue_filter():
    """Test venue filter adds source keyword."""
    api = ScholarlyAPI()

    mock_results = [
        {"title": "Conference Paper", "year": 2023},
    ]

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)

        filter_obj = SearchFilter(venue="NeurIPS", year_from=2020)
        results = await api.search("neural networks", limit=10, filter=filter_obj)

        # Verify the enhanced query includes source filter
        call_args = mock_search.call_args.args
        enhanced_query = call_args[0]
        assert "source:NeurIPS" in enhanced_query

    await api.close()


@pytest.mark.asyncio
async def test_search_error_handling():
    """Test graceful error handling."""
    api = ScholarlyAPI()

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        # Simulate anti-bot or network error
        mock_search.side_effect = Exception("Captcha required")

        results = await api.search("test query", limit=10)

        # Should return empty list on error (graceful handling)
        assert results == []

    await api.close()


@pytest.mark.asyncio
async def test_search_limit():
    """Test that limit is applied to results."""
    api = ScholarlyAPI()

    mock_results = [
        {"title": f"Paper {i}", "year": 2023} for i in range(100)
    ]

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)

        results = await api.search("test", limit=5)

        assert len(results) == 5

    await api.close()


@pytest.mark.asyncio
async def test_search_default_filter():
    """Test search with default SearchFilter (no filter provided)."""
    api = ScholarlyAPI()

    mock_results = [{"title": "Recent Paper", "year": 2023}]

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)

        # No filter provided - should create default
        results = await api.search("test query", limit=10)

        assert len(results) == 1

        # Verify default year_from is applied (after:{year})
        call_args = mock_search.call_args.args
        enhanced_query = call_args[0]
        # Should have "after:" with default year (current year - 2)
        assert "after:" in enhanced_query

    await api.close()


@pytest.mark.asyncio
async def test_search_only_year_from():
    """Test search with only year_from filter."""
    api = ScholarlyAPI()

    mock_results = [{"title": "Paper", "year": 2023}]

    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)

        filter_obj = SearchFilter(year_from=2020, year_to=None)
        results = await api.search("test", limit=10, filter=filter_obj)

        call_args = mock_search.call_args.args
        enhanced_query = call_args[0]
        assert "after:2020" in enhanced_query
        assert "before:" not in enhanced_query

    await api.close()