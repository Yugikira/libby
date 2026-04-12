"""Tests for Serpapi API."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.serpapi import SerpapiAPI, SerpapiConfirmationNeeded


@pytest.mark.asyncio
async def test_get_pdf_url_success():
    """Test successful PDF link from Google Scholar."""
    api = SerpapiAPI()

    mock_response = {
        "organic_results": [
            {
                "title": "Test Paper",
                "link": "https://example.com/paper.pdf",
            },
        ],
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url = await api.get_pdf_url("10.1234/test", "test-api-key")

        assert pdf_url == "https://example.com/paper.pdf"


@pytest.mark.asyncio
async def test_get_pdf_url_from_resources():
    """Test PDF from resources list."""
    api = SerpapiAPI()

    mock_response = {
        "organic_results": [
            {
                "title": "Test Paper",
                "link": "https://example.com/paper",
                "resources": [
                    {"file_format": "PDF", "link": "https://example.com/paper.pdf"},
                ],
            },
        ],
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url = await api.get_pdf_url("10.1234/test", "test-api-key")

        assert pdf_url == "https://example.com/paper.pdf"


@pytest.mark.asyncio
async def test_get_pdf_url_not_found():
    """Test when no PDF link found."""
    api = SerpapiAPI()

    mock_response = {
        "organic_results": [
            {"title": "Test Paper", "link": "https://example.com/paper"},
        ],
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url = await api.get_pdf_url("10.1234/test", "test-api-key")

        assert pdf_url is None


@pytest.mark.asyncio
async def test_get_pdf_url_api_error():
    """Test API error response."""
    api = SerpapiAPI()

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"error": "Invalid API key"}

        pdf_url = await api.get_pdf_url("10.1234/test", "invalid-key")

        assert pdf_url is None


# Tests for search() method

@pytest.mark.asyncio
async def test_search_quota_reached():
    """Test quota detection returns (results, True)."""
    api = SerpapiAPI()

    # First call succeeds, second call hits quota
    mock_responses = [
        {
            "organic_results": [
                {"title": "Paper 1", "link": "https://example.com/paper1.pdf"},
            ],
        },
        {"error": "Invalid API key"},
    ]

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = mock_responses

        results, quota_reached = await api.search("test query", "test-api-key", max_pages=2)

        assert quota_reached is True
        assert len(results) == 1
        assert results[0]["title"] == "Paper 1"


@pytest.mark.asyncio
async def test_search_pagination():
    """Test multi-page search (2 pages)."""
    api = SerpapiAPI()

    mock_responses = [
        {
            "organic_results": [
                {"title": f"Paper {i}", "link": f"https://example.com/paper{i}.pdf"}
                for i in range(1, 11)
            ],
        },
        {
            "organic_results": [
                {"title": f"Paper {i}", "link": f"https://example.com/paper{i}.pdf"}
                for i in range(11, 21)
            ],
        },
    ]

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = mock_responses

        results, quota_reached = await api.search("test query", "test-api-key", max_pages=2)

        assert quota_reached is False
        assert len(results) == 20
        assert mock_get.call_count == 2
        # Verify pagination params: first call start=0, second call start=10
        first_call_params = mock_get.call_args_list[0][1]["params"]
        assert first_call_params["start"] == 0
        second_call_params = mock_get.call_args_list[1][1]["params"]
        assert second_call_params["start"] == 10


@pytest.mark.asyncio
async def test_search_error_retry():
    """Test retry on transient error."""
    api = SerpapiAPI()

    # First call fails, retry succeeds, second page succeeds
    mock_responses = [
        Exception("Network error"),
        {
            "organic_results": [
                {"title": "Paper 1", "link": "https://example.com/paper1.pdf"},
            ],
        },
        {
            "organic_results": [
                {"title": "Paper 2", "link": "https://example.com/paper2.pdf"},
            ],
        },
    ]

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = mock_responses

        results, quota_reached = await api.search("test query", "test-api-key", max_pages=2)

        assert quota_reached is False
        assert len(results) == 2


@pytest.mark.asyncio
async def test_search_no_results():
    """Test empty results."""
    api = SerpapiAPI()

    mock_response = {"organic_results": []}

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        results, quota_reached = await api.search("nonexistent query", "test-api-key")

        assert quota_reached is False
        assert len(results) == 0
