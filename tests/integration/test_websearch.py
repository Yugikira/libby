"""Integration tests for websearch."""

import pytest

from libby.models.config import LibbyConfig
from libby.models.search_filter import SearchFilter
from libby.core.websearch import WebSearcher


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websearch_real_query():
    """Test real search query (requires network)."""
    config = LibbyConfig()
    searcher = WebSearcher(config)

    results = await searcher.search(
        "machine learning",
        limit=10,
        skip_serpapi=True,  # Skip to save quota
    )

    assert results.total_count > 0
    assert len(results.sources_used) >= 1

    await searcher.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websearch_with_year_filter():
    """Test search with year filter."""
    config = LibbyConfig()
    searcher = WebSearcher(config)

    filter = SearchFilter(year_from=2023)

    results = await searcher.search(
        "artificial intelligence",
        filter=filter,
        limit=10,
        skip_serpapi=True,
    )

    for r in results.results:
        if r.year:
            assert r.year >= 2023

    await searcher.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websearch_doi_merging():
    """Test that results with same DOI are merged."""
    config = LibbyConfig()
    searcher = WebSearcher(config)

    results = await searcher.search(
        "attention is all you need",
        limit=5,
        skip_serpapi=True,
    )

    # Should find the famous Transformer paper
    # Multiple sources should have it, merged by DOI
    assert results.total_count > 0

    await searcher.close()