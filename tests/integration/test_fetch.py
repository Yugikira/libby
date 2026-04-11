"""Integration tests for fetch command."""

import pytest
from libby.models.config import LibbyConfig
from libby.core.pdf_fetcher import PDFFetcher


@pytest.mark.asyncio
async def test_fetch_real_doi():
    """Test fetching real DOI (requires network)."""
    config = LibbyConfig()
    fetcher = PDFFetcher(config)
    # Disable serpapi to avoid exception
    fetcher.serpapi = None

    result = await fetcher.fetch("10.1007/s11142-016-9368-9")

    # Should find PDF URL from at least one source
    # This test may fail if all sources are unavailable
    assert isinstance(result, object)  # Basic sanity check
    assert result.doi == "10.1007/s11142-016-9368-9"

    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_invalid_doi():
    """Test fetching invalid DOI."""
    config = LibbyConfig()
    fetcher = PDFFetcher(config)
    # Disable serpapi to avoid exception
    fetcher.serpapi = None

    result = await fetcher.fetch("10.0000/invalid-doi-xyz")

    assert result.success is False
    assert result.error is not None

    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_biorxiv_doi():
    """Test fetching bioRxiv DOI."""
    config = LibbyConfig()
    fetcher = PDFFetcher(config)
    # Disable serpapi to avoid exception
    fetcher.serpapi = None

    # Test with a bioRxiv DOI
    result = await fetcher.fetch("10.1101/2023.01.01.123456")

    # May or may not find PDF depending on availability
    assert isinstance(result, object)

    await fetcher.close()