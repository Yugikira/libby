"""Tests for Crossref API client."""

import pytest
from unittest.mock import AsyncMock, patch

from libby.api.crossref import CrossrefAPI
from libby.models.search_filter import SearchFilter


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


@pytest.mark.asyncio
async def test_get_oa_link():
    """Test Crossref OA link extraction."""
    client = CrossrefAPI()

    # Test DOI with known OA link
    pdf_url, meta = await client.get_oa_link("10.1007/s11142-016-9368-9")

    # Should find PDF URL or return None (depends on actual metadata)
    # This test documents the expected behavior
    assert isinstance(meta, dict)

    await client.close()


@pytest.mark.asyncio
async def test_get_oa_link_not_found():
    """Test DOI without OA link."""
    client = CrossrefAPI()

    # Test with invalid DOI
    pdf_url, meta = await client.get_oa_link("10.0000/invalid-doi")

    assert pdf_url is None
    assert meta == {}

    await client.close()


@pytest.mark.asyncio
async def test_search_with_filter():
    """Test search with SearchFilter year range."""
    client = CrossrefAPI()

    # Mock the get method
    mock_response = {
        "status": "ok",
        "message": {
            "items": [
                {"DOI": "10.1234/test1", "title": ["Test Paper 1"]},
                {"DOI": "10.1234/test2", "title": ["Test Paper 2"]},
            ]
        },
    }

    with pytest.MonkeyPatch.context() as m:
        client.get = AsyncMock(return_value=mock_response)

        filter_obj = SearchFilter(year_from=2020, year_to=2024)
        results = await client.search("machine learning", rows=20, filter=filter_obj)

        # Verify results
        assert len(results) == 2
        assert results[0]["DOI"] == "10.1234/test1"

        # Verify filter params were correctly formatted
        call_args = client.get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        filter_param = params.get("filter", "")

        # Should contain year range filters
        assert "from-pub-date:2020" in filter_param
        assert "until-pub-date:2024" in filter_param

    await client.close()


@pytest.mark.asyncio
async def test_search_with_issn():
    """Test search with ISSN filter."""
    client = CrossrefAPI()

    # Mock the get method
    mock_response = {
        "status": "ok",
        "message": {
            "items": [
                {"DOI": "10.1234/nature1", "title": ["Nature Paper"]},
            ]
        },
    }

    with pytest.MonkeyPatch.context() as m:
        client.get = AsyncMock(return_value=mock_response)

        filter_obj = SearchFilter(issn="0028-0836", year_from=2022)
        results = await client.search("climate change", rows=10, filter=filter_obj)

        # Verify results
        assert len(results) == 1
        assert results[0]["DOI"] == "10.1234/nature1"

        # Verify filter params were correctly formatted
        call_args = client.get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        filter_param = params.get("filter", "")

        # Should contain ISSN filter
        assert "issn:0028-0836" in filter_param
        assert "from-pub-date:2022" in filter_param

    await client.close()


@pytest.mark.asyncio
async def test_search_default_filter():
    """Test search with default SearchFilter (year_from auto-set)."""
    client = CrossrefAPI()

    # Mock the get method
    mock_response = {
        "status": "ok",
        "message": {"items": []},
    }

    with pytest.MonkeyPatch.context() as m:
        client.get = AsyncMock(return_value=mock_response)

        # No filter provided - should use default SearchFilter
        results = await client.search("test query")

        # Verify filter params were set with default year_from
        call_args = client.get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        filter_param = params.get("filter", "")

        # Default year_from should be current year - 2
        from datetime import datetime
        expected_year = datetime.now().year - 2
        assert f"from-pub-date:{expected_year}" in filter_param

    await client.close()


@pytest.mark.asyncio
async def test_search_with_native_params():
    """Test search with native_params passthrough."""
    client = CrossrefAPI()

    # Mock the get method
    mock_response = {
        "status": "ok",
        "message": {"items": []},
    }

    with pytest.MonkeyPatch.context() as m:
        client.get = AsyncMock(return_value=mock_response)

        filter_obj = SearchFilter(
            year_from=2023, native_params={"type": "journal-article"}
        )
        results = await client.search("test", filter=filter_obj)

        # Verify filter params include native params
        call_args = client.get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        filter_param = params.get("filter", "")

        assert "from-pub-date:2023" in filter_param
        assert "type:journal-article" in filter_param

    await client.close()