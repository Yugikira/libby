"""Tests for WebSearcher core orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from libby.core.websearch import WebSearcher
from libby.models.search_filter import SearchFilter
from libby.models.search_result import SearchResult, SearchResults, SerpapiExtraInfo
from libby.models.config import LibbyConfig


@pytest.fixture
def config():
    """Create test config."""
    return LibbyConfig()


@pytest.fixture
def mock_crossref_results():
    """Sample Crossref API results."""
    return [
        {
            "DOI": "10.1234/crossref1",
            "title": ["Test Paper from Crossref"],
            "author": [{"family": "Smith", "given": "John"}],
            "published-print": {"date-parts": [[2023]]},
            "container-title": ["Journal of Testing"],
            "abstract": "Short abstract",
        },
        {
            "DOI": "10.1234/merged",
            "title": ["Merged Paper"],
            "author": [{"family": "Jones", "given": "Alice"}],
            "published-print": {"date-parts": [[2022]]},
            "container-title": ["Science"],
            "abstract": "Crossref abstract",
        },
    ]


@pytest.fixture
def mock_s2_results():
    """Sample Semantic Scholar API results."""
    return [
        {
            "externalIds": {"DOI": "10.1234/s2_paper"},
            "title": "S2 Paper Title",
            "year": 2023,
            "authors": [{"name": "Doe, Jane"}],
            "abstract": "S2 abstract",
            "venue": "ICML",
        },
        {
            "externalIds": {"DOI": "10.1234/merged"},
            "title": "Merged Paper: Extended Version",
            "year": 2022,
            "authors": [{"name": "Jones, Alice"}],
            "abstract": "Semantic Scholar abstract with more details",
            "venue": "Science Journal",
        },
    ]


@pytest.fixture
def mock_scholarly_results():
    """Sample Scholarly API results."""
    return [
        {
            "bib": {
                "title": "Scholarly Paper",
                "pub_year": "2023",
            },
            "author": ["Williams, Bob"],
            "url_scholarbib": "https://scholar.google.com/scholar?q=10.1234/scholarly",
        },
        {
            "bib": {
                "title": "Merged Paper",
                "pub_year": "2022",
            },
            "author": ["Jones, Alice"],
            "pub_url": "https://example.com/paper",
        },
    ]


@pytest.fixture
def mock_serpapi_results():
    """Sample Serpapi API results."""
    return [
        {
            "title": "Serpapi Paper",
            "link": "https://example.com/serpapi1",
            "publication_info": {
                "doi": "10.1234/serpapi1",
            },
            "resources": [
                {"file_format": "PDF", "link": "https://example.com/pdf1.pdf"}
            ],
        },
        {
            "title": "Another Paper",
            "link": "https://example.com/serpapi2",
            "publication_info": {
                "summary": "Published in Nature, 2023",
            },
        },
    ]


@pytest.mark.asyncio
async def test_search_parallel_execution(config, mock_crossref_results, mock_s2_results, mock_scholarly_results):
    """Test that parallel search executes all three APIs concurrently."""
    searcher = WebSearcher(config)

    # Mock all three APIs
    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                mock_cr.return_value = mock_crossref_results
                mock_s2.return_value = mock_s2_results
                mock_sch.return_value = mock_scholarly_results

                # Execute search (skip serpapi)
                results = await searcher.search("test query", limit=10, skip_serpapi=True)

                # Verify all three APIs were called
                mock_cr.assert_called_once()
                mock_s2.assert_called_once()
                mock_sch.assert_called_once()

                # Verify sources used
                assert "crossref" in results.sources_used
                assert "semantic_scholar" in results.sources_used
                assert "scholarly" in results.sources_used

    await searcher.close()


@pytest.mark.asyncio
async def test_merge_by_doi(config, mock_crossref_results, mock_s2_results):
    """Test DOI merging keeps longer values."""
    searcher = WebSearcher(config)

    # Mock APIs with overlapping DOI
    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                mock_cr.return_value = mock_crossref_results
                mock_s2.return_value = mock_s2_results
                mock_sch.return_value = []  # No scholarly results

                results = await searcher.search("test query", skip_serpapi=True)

                # Find merged result
                merged = None
                for r in results.results:
                    if r.doi == "10.1234/merged":
                        merged = r
                        break

                assert merged is not None

                # Longer title should be kept (S2 has longer title)
                assert merged.title == "Merged Paper: Extended Version"

                # Longer abstract should be kept (S2 has longer abstract)
                assert "Semantic Scholar abstract" in merged.abstract

                # Both sources should be tracked
                assert "crossref" in merged.sources
                assert "semantic_scholar" in merged.sources

    await searcher.close()


@pytest.mark.asyncio
async def test_serpapi_quota_reached(config, mock_crossref_results, mock_s2_results, mock_scholarly_results, mock_serpapi_results):
    """Test quota warning when Serpapi quota reached."""
    # Set SERPAPI_API_KEY environment variable for this test
    with patch.dict(os.environ, {"SERPAPI_API_KEY": "test_key"}):
        searcher = WebSearcher(config)
        assert searcher.serpapi is not None

        # Mock console.print to capture output
        mock_print = MagicMock()
        searcher.console.print = mock_print

        with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
            with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
                with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                    with patch.object(searcher.serpapi, 'search', new_callable=AsyncMock) as mock_ser:
                        mock_cr.return_value = mock_crossref_results
                        mock_s2.return_value = mock_s2_results
                        mock_sch.return_value = mock_scholarly_results
                        # Quota reached returns results with quota_reached=True
                        mock_ser.return_value = (mock_serpapi_results, True)

                        results = await searcher.search("test query", skip_serpapi=False)

                        # Quota warning should be shown
                        mock_print.assert_called()

    await searcher.close()


@pytest.mark.asyncio
async def test_serpapi_disabled_when_no_key(config, mock_crossref_results, mock_s2_results, mock_scholarly_results):
    """Test that Serpapi is skipped when no API key."""
    # Remove SERPAPI_API_KEY from environment
    with patch.dict(os.environ, {"SERPAPI_API_KEY": ""}, clear=True):
        searcher = WebSearcher(config)
        assert searcher.serpapi is None

        with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
            with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
                with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                    mock_cr.return_value = mock_crossref_results
                    mock_s2.return_value = mock_s2_results
                    mock_sch.return_value = mock_scholarly_results

                    results = await searcher.search("test query", skip_serpapi=False)

                    # Serpapi should not be in sources used
                    assert "serpapi" not in results.sources_used
                    assert len(results.serpapi_extra) == 0

    await searcher.close()


@pytest.mark.asyncio
async def test_serpapi_creates_extra_info(config, mock_crossref_results, mock_s2_results, mock_scholarly_results, mock_serpapi_results):
    """Test Serpapi creates SerpapiExtraInfo for each result."""
    searcher = WebSearcher(config)

    with patch.dict(os.environ, {"SERPAPI_API_KEY": "test_key"}):
        searcher = WebSearcher(config)

        with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
            with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
                with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                    with patch.object(searcher.serpapi, 'search', new_callable=AsyncMock) as mock_ser:
                        mock_cr.return_value = mock_crossref_results
                        mock_s2.return_value = mock_s2_results
                        mock_sch.return_value = mock_scholarly_results
                        mock_ser.return_value = (mock_serpapi_results, False)

                        results = await searcher.search("test query", skip_serpapi=False)

                        # Serpapi extra info should be populated
                        assert len(results.serpapi_extra) > 0
                        assert results.serpapi_extra[0].link == "https://example.com/serpapi1"

    await searcher.close()


@pytest.mark.asyncio
async def test_parse_crossref(config):
    """Test Crossref result parsing."""
    searcher = WebSearcher(config)

    crossref_item = {
        "DOI": "10.1234/test",
        "title": ["Test Title"],
        "author": [{"family": "Smith", "given": "John"}, {"family": "Doe", "given": "Jane"}],
        "published-print": {"date-parts": [[2023, 5]]},
        "container-title": ["Nature"],
        "abstract": "Test abstract",
        "volume": "10",
        "issue": "2",
        "page": "100-110",
        "publisher": "Nature Publishing",
        "URL": "https://doi.org/10.1234/test",
    }

    result = searcher._parse_crossref(crossref_item)

    assert result.doi == "10.1234/test"
    assert result.title == "Test Title"
    assert result.author == ["Smith, John", "Doe, Jane"]
    assert result.year == 2023
    assert result.journal == "Nature"
    assert result.abstract == "Test abstract"
    assert result.volume == "10"
    assert result.number == "2"
    assert result.pages == "100-110"
    assert result.publisher == "Nature Publishing"
    assert result.url == "https://doi.org/10.1234/test"
    assert "crossref" in result.sources


@pytest.mark.asyncio
async def test_parse_semantic_scholar(config):
    """Test Semantic Scholar result parsing."""
    searcher = WebSearcher(config)

    s2_item = {
        "externalIds": {"DOI": "10.1234/s2test"},
        "title": "S2 Title",
        "year": 2024,
        "authors": [{"name": "Alice Jones"}, {"name": "Bob Smith"}],
        "abstract": "S2 abstract",
        "venue": "ICML 2024",
        "journal": "Journal of ML Research",
    }

    result = searcher._parse_s2(s2_item)

    assert result.doi == "10.1234/s2test"
    assert result.title == "S2 Title"
    assert result.author == ["Alice Jones", "Bob Smith"]
    assert result.year == 2024
    assert result.journal == "ICML 2024"  # venue takes priority
    assert result.abstract == "S2 abstract"
    assert "semantic_scholar" in result.sources


@pytest.mark.asyncio
async def test_parse_scholarly(config):
    """Test Scholarly result parsing."""
    searcher = WebSearcher(config)

    scholarly_item = {
        "bib": {
            "title": "Scholarly Title",
            "pub_year": "2023",
        },
        "author": ["Williams, Bob", "Brown, Charlie"],
        "pub_url": "https://example.com/paper",
    }

    result = searcher._parse_scholarly(scholarly_item)

    assert result.title == "Scholarly Title"
    assert result.author == ["Williams, Bob", "Brown, Charlie"]
    assert result.year == 2023
    assert result.url == "https://example.com/paper"
    assert "scholarly" in result.sources


@pytest.mark.asyncio
async def test_parse_serpapi(config):
    """Test Serpapi result parsing."""
    searcher = WebSearcher(config)

    serpapi_item = {
        "title": "Serpapi Title",
        "link": "https://example.com/paper",
        "publication_info": {
            "doi": "10.1234/serpapi",
        },
        "resources": [
            {"file_format": "PDF", "link": "https://example.com/pdf.pdf"}
        ],
        "cited_by": {"total": 42},
    }

    result = searcher._parse_serpapi(serpapi_item)

    assert result.title == "Serpapi Title"
    assert result.doi == "10.1234/serpapi"
    assert result.url == "https://example.com/paper"
    assert "serpapi" in result.sources


@pytest.mark.asyncio
async def test_extract_doi_from_serpapi(config):
    """Test DOI extraction from Serpapi results."""
    searcher = WebSearcher(config)

    # DOI in publication_info
    item1 = {"publication_info": {"doi": "10.1234/direct"}}
    assert searcher._extract_doi_from_serpapi(item1) == "10.1234/direct"

    # DOI in link URL
    item2 = {"link": "https://doi.org/10.1234/from_url"}
    assert searcher._extract_doi_from_serpapi(item2) == "10.1234/from_url"

    # No DOI
    item3 = {"link": "https://example.com/paper"}
    assert searcher._extract_doi_from_serpapi(item3) is None


@pytest.mark.asyncio
async def test_extract_pdf_link(config):
    """Test PDF link extraction from Serpapi results."""
    searcher = WebSearcher(config)

    # PDF in resources
    item1 = {
        "resources": [
            {"file_format": "PDF", "link": "https://example.com/pdf1.pdf"}
        ]
    }
    assert searcher._extract_pdf_link(item1) == "https://example.com/pdf1.pdf"

    # PDF link directly
    item2 = {"link": "https://example.com/pdf2.pdf"}
    assert searcher._extract_pdf_link(item2) == "https://example.com/pdf2.pdf"

    # No PDF
    item3 = {"link": "https://example.com/page.html"}
    assert searcher._extract_pdf_link(item3) is None


@pytest.mark.asyncio
async def test_search_with_filter(config, mock_crossref_results, mock_s2_results, mock_scholarly_results):
    """Test search passes filter to API clients."""
    searcher = WebSearcher(config)

    filter_obj = SearchFilter(year_from=2020, year_to=2024, venue="Nature")

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                mock_cr.return_value = mock_crossref_results
                mock_s2.return_value = mock_s2_results
                mock_sch.return_value = mock_scholarly_results

                results = await searcher.search("test", filter=filter_obj, skip_serpapi=True)

                # Verify filter was passed to each API
                cr_call = mock_cr.call_args
                assert cr_call.kwargs.get('filter') == filter_obj

                s2_call = mock_s2.call_args
                assert s2_call.kwargs.get('filter') == filter_obj

                sch_call = mock_sch.call_args
                assert sch_call.kwargs.get('filter') == filter_obj

    await searcher.close()


@pytest.mark.asyncio
async def test_search_handles_api_errors(config, mock_crossref_results):
    """Test that API errors are handled gracefully."""
    searcher = WebSearcher(config)

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                mock_cr.return_value = mock_crossref_results
                # S2 throws exception
                mock_s2.side_effect = Exception("S2 API error")
                mock_sch.return_value = []

                # Should still return Crossref results
                results = await searcher.search("test", skip_serpapi=True)

                assert len(results.results) > 0
                assert "crossref" in results.sources_used
                # S2 failed, should not be in sources
                assert "semantic_scholar" not in results.sources_used

    await searcher.close()


@pytest.mark.asyncio
async def test_search_results_no_doi(config):
    """Test handling results without DOI."""
    searcher = WebSearcher(config)

    # Results without DOI should still be included
    mock_cr_no_doi = [
        {"title": ["No DOI Paper"], "author": [{"family": "Test"}]},
        {"DOI": "10.1234/with_doi", "title": ["With DOI"]},
    ]

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                mock_cr.return_value = mock_cr_no_doi
                mock_s2.return_value = []
                mock_sch.return_value = []

                results = await searcher.search("test", skip_serpapi=True)

                # Both results should be present (one with DOI, one without)
                assert len(results.results) == 2

    await searcher.close()


@pytest.mark.asyncio
async def test_search_results_total_count(config, mock_crossref_results, mock_s2_results, mock_scholarly_results):
    """Test total_count reflects unique results."""
    searcher = WebSearcher(config)

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as mock_sch:
                mock_cr.return_value = mock_crossref_results  # 2 results, 1 merged
                mock_s2.return_value = mock_s2_results  # 2 results, 1 merged
                mock_sch.return_value = mock_scholarly_results  # 2 results

                results = await searcher.search("test", skip_serpapi=True)

                # Total should be unique results: crossref(2) + s2(2) + scholarly(2) - duplicates(1)
                # crossref: 10.1234/crossref1, 10.1234/merged
                # s2: 10.1234/s2_paper, 10.1234/merged
                # scholarly: no DOI papers (title-based)
                # Total unique: ~5 papers
                assert results.total_count == len(results.results)

    await searcher.close()