"""Tests for bioRxiv API."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.biorxiv import BiorxivAPI


@pytest.mark.asyncio
async def test_get_pdf_url_biorxiv():
    """Test bioRxiv DOI lookup."""
    api = BiorxivAPI()

    mock_response = {
        "collection": [
            {"doi": "10.1101/2023.01.01.123456", "version": 1},
            {"doi": "10.1101/2023.01.01.123456", "version": 2},
        ],
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        pdf_url = await api.get_pdf_url("10.1101/2023.01.01.123456")

        assert pdf_url == "https://www.biorxiv.org/content/10.1101/2023.01.01.123456v2.full.pdf"

    await api.close()


@pytest.mark.asyncio
async def test_get_pdf_url_not_biorxiv():
    """Test non-bioRxiv DOI."""
    api = BiorxivAPI()

    pdf_url = await api.get_pdf_url("10.1007/s11142-016-9368-9")

    assert pdf_url is None


@pytest.mark.asyncio
async def test_get_pdf_url_medrxiv():
    """Test medRxiv DOI lookup."""
    api = BiorxivAPI()

    mock_response = {
        "collection": [
            {"doi": "10.1101/2023.01.01.23287000", "version": 1},
        ],
    }

    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            Exception("Not found on biorxiv"),  # First call fails
            mock_response,  # Second call succeeds
        ]

        pdf_url = await api.get_pdf_url("10.1101/2023.01.01.23287000")

        assert pdf_url == "https://www.medrxiv.org/content/10.1101/2023.01.01.23287000v1.full.pdf"

    await api.close()
