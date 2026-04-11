"""Tests for Unpaywall API."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.unpaywall import UnpaywallAPI


@pytest.mark.asyncio
async def test_get_pdf_url_success():
    """Test successful PDF URL lookup."""
    api = UnpaywallAPI()

    mock_response = {
        "title": "Test Paper",
        "year": 2023,
        "best_oa_location": {
            "url_for_pdf": "https://example.com/paper.pdf",
            "host_type": "publisher",
        },
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url, meta = await api.get_pdf_url("10.1234/test", "test@example.com")

        assert pdf_url == "https://example.com/paper.pdf"
        assert meta["title"] == "Test Paper"
        assert meta["year"] == 2023

    await api.close()


@pytest.mark.asyncio
async def test_get_pdf_url_not_found():
    """Test when no OA location available."""
    api = UnpaywallAPI()

    mock_response = {
        "best_oa_location": None,
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url, meta = await api.get_pdf_url("10.1234/test", "test@example.com")

        assert pdf_url is None
        assert meta == {}

    await api.close()


@pytest.mark.asyncio
async def test_get_pdf_url_error_response():
    """Test error response from API."""
    api = UnpaywallAPI()

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"status": "error", "message": "DOI not found"}

        pdf_url, meta = await api.get_pdf_url("10.0000/invalid", "test@example.com")

        assert pdf_url is None
        assert meta == {}

    await api.close()
