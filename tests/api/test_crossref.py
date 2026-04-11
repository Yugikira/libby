"""Tests for Crossref API client."""

import pytest

from libby.api.crossref import CrossrefAPI


@pytest.mark.asyncio
async def test_fetch_by_doi():
    """Test fetching by DOI."""
    client = CrossrefAPI()
    doi = "10.1007/s11142-016-9368-9"
    result = await client.fetch_by_doi(doi)
    assert result is not None
    assert result.get("DOI") == doi
    await client.close()


@pytest.mark.asyncio
async def test_search_by_title():
    """Test searching by title."""
    client = CrossrefAPI(mailto="test@example.com")
    results = await client.search_by_title("corporate site visit")
    assert isinstance(results, list)
    await client.close()