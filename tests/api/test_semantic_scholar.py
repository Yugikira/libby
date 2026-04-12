"""Tests for Semantic Scholar API."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.semantic_scholar import SemanticScholarAPI


@pytest.mark.asyncio
async def test_get_pdf_url_success():
    """Test successful PDF URL lookup with openAccessPdf."""
    api = SemanticScholarAPI()

    mock_response = {
        "title": "Test Paper",
        "year": 2023,
        "openAccessPdf": {
            "url": "https://example.com/paper.pdf",
            "status": "OA",
        },
        "externalIds": {
            "ArXiv": "2301.12345",
        },
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url, meta, ext_ids = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://example.com/paper.pdf"
        assert meta["title"] == "Test Paper"
        assert ext_ids.get("ArXiv") == "2301.12345"

    await api.close()


@pytest.mark.asyncio
async def test_get_pdf_url_no_oa():
    """Test when paper has no open access PDF."""
    api = SemanticScholarAPI()

    mock_response = {
        "title": "Paywalled Paper",
        "year": 2023,
        "openAccessPdf": None,
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url, meta, ext_ids = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert meta["title"] == "Paywalled Paper"

    await api.close()


@pytest.mark.asyncio
async def test_get_pdf_url_with_api_key():
    """Test that API key is passed in headers."""
    api = SemanticScholarAPI(api_key="test-key")

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {}

        await api.get_pdf_url("10.1234/test")

        # Verify get was called with headers containing api_key
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("x-api-key") == "test-key"

    await api.close()


# ============================================
# Tests for search() method
# ============================================


@pytest.mark.asyncio
async def test_search_with_year_filter():
    """Test search with year range filter."""
    from libby.models.search_filter import SearchFilter

    api = SemanticScholarAPI()

    mock_response = {
        "data": [
            {"title": "Paper 1", "year": 2023},
            {"title": "Paper 2", "year": 2024},
        ]
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        filter_obj = SearchFilter(year_from=2020, year_to=2024)
        results = await api.search("machine learning", limit=50, filter=filter_obj)

        assert len(results) == 2
        assert results[0]["title"] == "Paper 1"

        # Verify the year param is correctly formatted
        call_kwargs = mock_get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("year") == "2020-2024"

    await api.close()


@pytest.mark.asyncio
async def test_search_with_venue_filter():
    """Test search with venue filter."""
    from libby.models.search_filter import SearchFilter

    api = SemanticScholarAPI()

    mock_response = {
        "data": [
            {"title": "Conference Paper", "year": 2023, "venue": "NeurIPS"},
        ]
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        filter_obj = SearchFilter(venue="NeurIPS", year_from=2020)
        results = await api.search("deep learning", limit=10, filter=filter_obj)

        assert len(results) == 1

        # Verify the venue param is passed correctly
        call_kwargs = mock_get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("venue") == "NeurIPS"

    await api.close()


@pytest.mark.asyncio
async def test_search_with_api_key():
    """Test that API key is passed in headers for search."""
    api = SemanticScholarAPI(api_key="s2-api-key-123")

    mock_response = {"data": []}

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        await api.search("test query")

        # Verify API key is in headers
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs.get("headers", {}).get("x-api-key") == "s2-api-key-123"

    await api.close()


@pytest.mark.asyncio
async def test_search_error_response():
    """Test error handling for search."""
    api = SemanticScholarAPI()

    mock_response = {"error": "Rate limit exceeded"}

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        results = await api.search("test query")

        # Should return empty list on error
        assert results == []

    await api.close()


@pytest.mark.asyncio
async def test_search_default_filter():
    """Test search with default SearchFilter (no filter provided)."""
    api = SemanticScholarAPI()

    mock_response = {"data": [{"title": "Recent Paper"}]}

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # No filter provided - should create default with year_from
        results = await api.search("test query")

        assert len(results) == 1

        # Verify default year_from is set (current year - 2)
        call_kwargs = mock_get.call_args.kwargs
        params = call_kwargs.get("params", {})
        # Should have a year param (single year since year_to is None)
        assert "year" in params

    await api.close()
