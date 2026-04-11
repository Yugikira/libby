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
