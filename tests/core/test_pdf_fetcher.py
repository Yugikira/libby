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
    """Test Crossref OA is tried first and download succeeds."""
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as mock_crossref:
        mock_crossref.return_value = ("https://crossref.org/paper.pdf", {"title": "Test"})
        # Mock download to succeed
        with patch.object(fetcher, '_try_download', new_callable=AsyncMock) as mock_download:
            mock_download.return_value = True

            result = await fetcher.fetch("10.1234/test")

            assert result.success is True
            assert result.source == "crossref_oa"
            assert mock_crossref.called
            assert mock_download.called


@pytest.mark.asyncio
async def test_fetch_crossref_download_fail_continue_to_unpaywall(fetcher):
    """Test Unpaywall is tried when Crossref URL download fails."""
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as mock_crossref:
        mock_crossref.return_value = ("https://crossref.org/paper.pdf", {"title": "Test"})
        with patch.object(fetcher.unpaywall, 'get_pdf_url', new_callable=AsyncMock) as mock_unpaywall:
            mock_unpaywall.return_value = ("https://unpaywall.org/paper.pdf", {"title": "Test2"})
            with patch.object(fetcher, '_try_download', new_callable=AsyncMock) as mock_download:
                # Crossref download fails, Unpaywall succeeds
                mock_download.side_effect = [False, True]

                result = await fetcher.fetch("10.1234/test")

                assert result.success is True
                assert result.source == "unpaywall"
                assert mock_download.call_count == 2


@pytest.mark.asyncio
async def test_fetch_no_source_found(fetcher):
    """Test when all sources fail."""
    # Mock all sources to return None or fail
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as m1:
        m1.return_value = (None, {})
        with patch.object(fetcher.s2, 'get_pdf_url', new_callable=AsyncMock) as m2:
            m2.return_value = (None, {}, {})
            with patch.object(fetcher.core, 'get_pdf_url', new_callable=AsyncMock) as m5:
                m5.return_value = (None, {})
                with patch.object(fetcher.biorxiv, 'get_pdf_url', new_callable=AsyncMock) as m3:
                    m3.return_value = None
                    with patch.object(fetcher.scihub, 'get_pdf_url', new_callable=AsyncMock) as m4:
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


@pytest.mark.asyncio
async def test_fetch_core_succeeds_after_s2_fails(fetcher):
    """Test CORE is tried when S2 URL download fails."""
    with patch.object(fetcher.crossref, 'get_oa_link', new_callable=AsyncMock) as m1:
        m1.return_value = (None, {})
        with patch.object(fetcher.s2, 'get_pdf_url', new_callable=AsyncMock) as m2:
            # S2 returns URL but download fails (e.g., paywall 403)
            m2.return_value = ("https://wiley.com/paper.pdf", {"title": "Test"}, {})
            with patch.object(fetcher.core, 'get_pdf_url', new_callable=AsyncMock) as m3:
                m3.return_value = ("https://core.ac.uk/download/123.pdf", {"title": "Test"})
                with patch.object(fetcher, '_try_download', new_callable=AsyncMock) as m_download:
                    # S2 download fails, CORE succeeds
                    m_download.side_effect = [False, True]

                    result = await fetcher.fetch("10.1234/test")

                    assert result.success is True
                    assert result.source == "core"
                    assert m_download.call_count == 2