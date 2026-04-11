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
