"""Tests for Sci-hub API."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from libby.api.scihub import ScihubAPI, MANUAL_DOWNLOAD_HINT


@pytest.mark.asyncio
async def test_get_pdf_url_success():
    """Test successful PDF URL extraction with embed tag."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <embed src="https://sci-hub.ru/paper.pdf" type="application/pdf">
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://sci-hub.ru/paper.pdf"
        assert error is None


@pytest.mark.asyncio
async def test_get_pdf_url_iframe_fallback():
    """Test iframe fallback pattern."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <iframe src="https://sci-hub.ru/paper.pdf"></iframe>
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://sci-hub.ru/paper.pdf"
        assert error is None


@pytest.mark.asyncio
async def test_get_pdf_url_relative_url():
    """Test protocol-relative URL handling."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <embed src="//sci-hub.ru/paper.pdf" type="application/pdf">
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://sci-hub.ru/paper.pdf"
        assert error is None


@pytest.mark.asyncio
async def test_get_pdf_url_downloads_path():
    """Test /downloads path handling."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <embed src="/downloads/paper.pdf" type="application/pdf">
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url == "https://sci-hub.ru/downloads/paper.pdf"
        assert error is None


@pytest.mark.asyncio
async def test_get_pdf_url_captcha_detected():
    """Test CAPTCHA detection returns manual download hint."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <body>
    <div class="g-recaptcha"></div>
    </body>
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert error is not None
        assert "CAPTCHA" in error or "blocked" in error
        assert "Manual download" in error


@pytest.mark.asyncio
async def test_get_pdf_url_not_found():
    """Test when PDF URL not found in HTML."""
    api = ScihubAPI()

    mock_html = "<html><body>No PDF here</body></html>"

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert error is not None
        assert "no pdf url found" in error.lower()


@pytest.mark.asyncio
async def test_get_pdf_url_network_error():
    """Test network error handling returns error message."""
    api = ScihubAPI()

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.side_effect = Exception("Connection failed")

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert error is not None
        assert "Request failed" in error


@pytest.mark.asyncio
async def test_get_pdf_url_page_fetch_failed():
    """Test when page fetch returns None."""
    api = ScihubAPI()

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = None

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert error is not None
        assert "Failed to fetch page" in error


@pytest.mark.asyncio
async def test_get_pdf_url_timeout():
    """Test timeout handling."""
    api = ScihubAPI()

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.side_effect = asyncio.TimeoutError()

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert error is not None
        assert "timed out" in error.lower()
        assert "Manual download" in error


@pytest.mark.asyncio
async def test_blocked_page_detection_cloudflare():
    """Test Cloudflare block detection."""
    api = ScihubAPI()

    mock_html = """
    <html>
    <body>
    <div class="cloudflare">Access denied</div>
    </body>
    </html>
    """

    with patch.object(api, 'get_html', new_callable=AsyncMock) as mock_get_html:
        mock_get_html.return_value = mock_html

        pdf_url, error = await api.get_pdf_url("10.1234/test")

        assert pdf_url is None
        assert error is not None
        assert "blocked" in error.lower()


@pytest.mark.asyncio
async def test_custom_scihub_url():
    """Test custom Sci-hub URL."""
    api = ScihubAPI(scihub_url="https://sci-hub.se")

    assert api.scihub_url == "https://sci-hub.se"