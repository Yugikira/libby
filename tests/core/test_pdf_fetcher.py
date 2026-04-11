"""Tests for PDFFetcher cascade orchestration."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.models.config import LibbyConfig
from libby.core.pdf_fetcher import PDFFetcher


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = LibbyConfig()
    config.scihub_url = "https://sci-hub.ru"
    return config


@pytest.fixture
def fetcher(mock_config):
    """Create PDFFetcher with mocked dependencies."""
    return PDFFetcher(mock_config)


@pytest.mark.asyncio
async def test_fetch_crossref_priority(fetcher):
    """Test Crossref OA is tried first."""
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as mock_crossref:
        mock_crossref.return_value = ("https://crossref.org/paper.pdf", {"title": "Test"})

        result = await fetcher.fetch("10.1234/test")

        assert result.success is True
        assert result.source == "crossref_oa"
        assert mock_crossref.called


@pytest.mark.asyncio
async def test_fetch_unpaywall_fallback(fetcher):
    """Test Unpaywall as fallback when Crossref fails."""
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as mock_crossref:
        mock_crossref.return_value = (None, {})

        with patch.object(fetcher.unpaywall, 'get_pdf_url', new_callable=AsyncMock) as mock_unpaywall:
            mock_unpaywall.return_value = ("https://unpaywall.org/paper.pdf", {"title": "Test"})

            result = await fetcher.fetch("10.1234/test")

            assert result.success is True
            assert result.source == "unpaywall"


@pytest.mark.asyncio
async def test_fetch_no_source_found(fetcher):
    """Test when all sources fail."""
    # Mock all sources to return None
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as m1:
        m1.return_value = (None, {})
        with patch.object(fetcher.s2, 'get_pdf_url', new_callable=AsyncMock) as m2:
            m2.return_value = (None, {}, {})
            with patch.object(fetcher.biorxiv, 'get_pdf_url', new_callable=AsyncMock) as m3:
                m3.return_value = None
                with patch.object(fetcher.scihub, 'get_pdf_url', new_callable=AsyncMock) as m4:
                    # ScihubAPI returns tuple (pdf_url, error)
                    m4.return_value = (None, "No PDF found")
                    # Mock Selenium downloader to also fail
                    with patch.object(fetcher, '_get_selenium_downloader') as mock_selenium:
                        mock_downloader = mock_selenium.return_value
                        mock_downloader.download_pdf.return_value = (None, "Selenium failed")
                        # Mock serpapi to None to avoid exception
                        fetcher.serpapi = None

                        result = await fetcher.fetch("10.1234/test")

                        assert result.success is False
                        assert "Selenium failed" in result.error
