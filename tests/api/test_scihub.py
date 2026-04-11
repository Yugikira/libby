"""Tests for Sci-hub API."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.scihub import ScihubAPI


@pytest.mark.asyncio
async def test_get_pdf_url_success():
    """Test successful PDF URL extraction."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <iframe src="https://sci-hub.ru/paper.pdf"></iframe>
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://sci-hub.ru/paper.pdf"


@pytest.mark.asyncio
async def test_get_pdf_url_relative_url():
    """Test protocol-relative URL handling."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <iframe src="//sci-hub.ru/paper.pdf"></iframe>
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://sci-hub.ru/paper.pdf"


@pytest.mark.asyncio
async def test_get_pdf_url_not_found():
    """Test when PDF URL not found in HTML."""
    api = ScihubAPI()

    mock_html = "<html><body>No PDF here</body></html>"

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None


@pytest.mark.asyncio
async def test_get_pdf_url_network_error():
    """Test network error handling."""
    api = ScihubAPI()

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.side_effect = Exception("Connection failed")

        pdf_url = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
