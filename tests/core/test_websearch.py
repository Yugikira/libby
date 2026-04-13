"""Tests for WebSearcher core orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from libby.core.websearch import WebSearcher
from libby.models.search_filter import SearchFilter
from libby.models.search_result import SearchResult, SearchResults, SerpapiExtraInfo, parse_bibtex
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
async def test_search_parallel_execution(config, mock_crossref_results, mock_s2_results):
    """Test that parallel search executes both APIs concurrently."""
    searcher = WebSearcher(config)

    # Mock both APIs
    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = mock_crossref_results
            mock_s2.return_value = mock_s2_results

            # Execute search (skip serpapi)
            results = await searcher.search("test query", limit=10, skip_serpapi=True)

            # Verify both APIs were called
            mock_cr.assert_called_once()
            mock_s2.assert_called_once()

            # Verify sources used
            assert "crossref" in results.sources_used
            assert "s2" in results.sources_used

    await searcher.close()


@pytest.mark.asyncio
async def test_merge_by_doi(config, mock_crossref_results, mock_s2_results):
    """Test DOI merging keeps longer values."""
    searcher = WebSearcher(config)

    # Mock APIs with overlapping DOI
    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = mock_crossref_results
            mock_s2.return_value = mock_s2_results

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
            assert "s2" in merged.sources

    await searcher.close()


@pytest.mark.asyncio
async def test_serpapi_quota_reached(config, mock_crossref_results, mock_s2_results, mock_serpapi_results):
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
                with patch.object(searcher.serpapi, 'search', new_callable=AsyncMock) as mock_ser:
                    mock_cr.return_value = mock_crossref_results
                    mock_s2.return_value = mock_s2_results
                    # Quota reached returns results with quota_reached=True
                    mock_ser.return_value = (mock_serpapi_results, True)

                    results = await searcher.search("test query", skip_serpapi=False)

                    # Quota warning should be shown
                    mock_print.assert_called()

    await searcher.close()


@pytest.mark.asyncio
async def test_serpapi_disabled_when_no_key(config, mock_crossref_results, mock_s2_results):
    """Test that Serpapi is skipped when no API key."""
    # Remove SERPAPI_API_KEY from environment
    with patch.dict(os.environ, {"SERPAPI_API_KEY": ""}, clear=False):
        searcher = WebSearcher(config)
        assert searcher.serpapi is None

        with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
            with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
                mock_cr.return_value = mock_crossref_results
                mock_s2.return_value = mock_s2_results

                results = await searcher.search("test query", skip_serpapi=False)

                # Serpapi should not be in sources used
                assert "serpapi" not in results.sources_used
                assert len(results.serpapi_extra) == 0

    await searcher.close()


@pytest.mark.asyncio
async def test_serpapi_creates_extra_info(config, mock_crossref_results, mock_s2_results, mock_serpapi_results):
    """Test Serpapi creates SerpapiExtraInfo for each result."""
    with patch.dict(os.environ, {"SERPAPI_API_KEY": "test_key"}):
        searcher = WebSearcher(config)

        with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
            with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
                with patch.object(searcher.serpapi, 'search', new_callable=AsyncMock) as mock_ser:
                    mock_cr.return_value = mock_crossref_results
                    mock_s2.return_value = mock_s2_results
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
        "journal": {"name": "Journal of ML Research", "volume": "10", "pages": "100-110"},
    }

    result = searcher._parse_s2(s2_item)

    assert result.doi == "10.1234/s2test"
    assert result.title == "S2 Title"
    assert result.author == ["Alice Jones", "Bob Smith"]
    assert result.year == 2024
    assert result.journal == "Journal of ML Research"  # journal.name takes priority
    assert result.abstract == "S2 abstract"
    assert "s2" in result.sources


@pytest.mark.asyncio
async def test_parse_serpapi(config):
    """Test Serpapi result parsing - basic fields as fallback."""
    searcher = WebSearcher(config)

    serpapi_item = {
        "title": "Serpapi Title",
        "link": "https://example.com/paper",
        "snippet": "This is the abstract from snippet.",
        "publication_info": {
            "doi": "10.1234/serpapi",
            "summary": "2024 - Journal Name",
            "authors": [
                {"name": "John Smith"},
                {"name": "Jane Doe"},
            ],
        },
        "resources": [
            {"file_format": "PDF", "link": "https://example.com/pdf.pdf"}
        ],
        "cited_by": {"total": 42},
        "inline_links": {
            "serpapi_cite_link": "https://serpapi.com/cite?q=test"
        },
    }

    result = searcher._parse_serpapi(serpapi_item)

    # Basic fields extracted as fallback (if BibTeX fails)
    assert result.title == "Serpapi Title"
    assert result.abstract == "This is the abstract from snippet."
    assert result.author == ["John Smith", "Jane Doe"]
    assert result.year == 2024
    assert result.doi == "10.1234/serpapi"
    assert result.url == "https://example.com/paper"
    assert "serpapi" in result.sources

    # journal/volume/pages not extracted (from BibTeX)
    assert result.journal is None
    assert result.volume is None
    assert result.pages is None

    # Test BibTeX link extraction
    bibtex_link = searcher._extract_bibtex_link(serpapi_item)
    assert bibtex_link == "https://serpapi.com/cite?q=test"


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
async def test_search_with_filter(config, mock_crossref_results, mock_s2_results):
    """Test search passes filter to API clients."""
    searcher = WebSearcher(config)

    filter_obj = SearchFilter(year_from=2020, year_to=2024, venue="Nature")

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = mock_crossref_results
            mock_s2.return_value = mock_s2_results

            results = await searcher.search("test", filter=filter_obj, skip_serpapi=True)

            # Verify filter was passed to each API
            cr_call = mock_cr.call_args
            assert cr_call.kwargs.get('filter') == filter_obj

            s2_call = mock_s2.call_args
            assert s2_call.kwargs.get('filter') == filter_obj

    await searcher.close()


@pytest.mark.asyncio
async def test_search_handles_api_errors(config, mock_crossref_results):
    """Test that API errors are handled gracefully."""
    searcher = WebSearcher(config)

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = mock_crossref_results
            # S2 throws exception
            mock_s2.side_effect = Exception("S2 API error")

            # Should still return Crossref results
            results = await searcher.search("test", skip_serpapi=True)

            assert len(results.results) > 0
            assert "crossref" in results.sources_used
            # S2 failed, should not be in sources
            assert "s2" not in results.sources_used

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
            mock_cr.return_value = mock_cr_no_doi
            mock_s2.return_value = []

            results = await searcher.search("test", skip_serpapi=True)

            # Both results should be present (one with DOI, one without)
            assert len(results.results) == 2

    await searcher.close()


@pytest.mark.asyncio
async def test_search_results_total_count(config, mock_crossref_results, mock_s2_results):
    """Test total_count reflects unique results."""
    searcher = WebSearcher(config)

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = mock_crossref_results  # 2 results, 1 merged
            mock_s2.return_value = mock_s2_results  # 2 results, 1 merged

            results = await searcher.search("test", skip_serpapi=True)

            # Total should be unique results: crossref(2) + s2(2) - duplicates(1)
            # crossref: 10.1234/crossref1, 10.1234/merged
            # s2: 10.1234/s2_paper, 10.1234/merged
            # Total unique: 3 papers
            assert results.total_count == len(results.results)

    await searcher.close()


@pytest.mark.asyncio
async def test_filter_by_author(config):
    """Test author filtering with different name formats."""
    searcher = WebSearcher(config)

    results = [
        SearchResult(doi="10.1", title="Paper 1", author=["Smith, John", "Jones, Alice"]),
        SearchResult(doi="10.2", title="Paper 2", author=["John Smith", "Bob Brown"]),
        SearchResult(doi="10.3", title="Paper 3", author=["Williams, Charlie"]),
        SearchResult(doi="10.4", title="Paper 4", author=[]),
    ]

    # Test surname match (Smith, John format)
    filtered = searcher._filter_by_author(results, "Smith")
    assert len(filtered) == 2  # Smith, John and John Smith both match

    # Test partial match
    filtered = searcher._filter_by_author(results, "John")
    assert len(filtered) == 2  # Smith, John and John Smith

    # Test no match
    filtered = searcher._filter_by_author(results, "Unknown")
    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_search_with_author_filter(config):
    """Test search with author filter applies post-filtering."""
    searcher = WebSearcher(config)

    # Add author to mock results
    mock_cr_with_author = [
        {
            "DOI": "10.1234/crossref1",
            "title": ["Test Paper"],
            "author": [{"family": "Smith", "given": "John"}],
            "published-print": {"date-parts": [[2023]]},
        },
        {
            "DOI": "10.1234/crossref2",
            "title": ["Other Paper"],
            "author": [{"family": "Jones", "given": "Alice"}],
            "published-print": {"date-parts": [[2023]]},
        },
    ]

    filter_obj = SearchFilter(author="Smith")

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = mock_cr_with_author
            mock_s2.return_value = []

            results = await searcher.search("test", filter=filter_obj, skip_serpapi=True)

            # Only Smith paper should be in results
            assert len(results.results) == 1
            assert results.results[0].doi == "10.1234/crossref1"

    await searcher.close()


@pytest.mark.asyncio
async def test_calculate_similarity(config):
    """Test string similarity calculation."""
    searcher = WebSearcher(config)

    # High similarity
    assert searcher._calculate_similarity("Nature", "Nature") == 1.0

    # Medium similarity
    sim = searcher._calculate_similarity("Journal of Accounting Research", "Journal of Accounting Res")
    assert sim > 0.9

    # Low similarity
    sim = searcher._calculate_similarity("Nature", "Science")
    assert sim < 0.5


@pytest.mark.asyncio
async def test_resolve_journal_filter_venue_only(config):
    """Test journal resolution when only venue is provided."""
    searcher = WebSearcher(config)

    filter_obj = SearchFilter(venue="Nature")

    mock_journal_results = [
        {"title": "Nature", "ISSN": ["0028-0836", "1476-4687"]},
    ]

    with patch.object(searcher.crossref, 'search_journal_by_name', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_journal_results

        resolved = await searcher._resolve_journal_filter(filter_obj)

        assert resolved._resolved_issn == "0028-0836"
        assert resolved._resolved_venue == "Nature"

    await searcher.close()


@pytest.mark.asyncio
async def test_resolve_journal_filter_issn_only(config):
    """Test journal resolution when only ISSN is provided."""
    searcher = WebSearcher(config)

    filter_obj = SearchFilter(issn="0028-0836")

    mock_journal = {"title": "Nature", "ISSN": ["0028-0836", "1476-4687"]}

    with patch.object(searcher.crossref, 'get_journal_by_issn', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_journal

        resolved = await searcher._resolve_journal_filter(filter_obj)

        assert resolved._resolved_venue == "Nature"
        assert resolved._resolved_issn == "0028-0836"

    await searcher.close()


@pytest.mark.asyncio
async def test_resolve_journal_filter_both_match(config):
    """Test journal resolution when venue and ISSN both provided and match."""
    searcher = WebSearcher(config)

    filter_obj = SearchFilter(venue="Nature", issn="0028-0836")

    mock_journal = {"title": "Nature", "ISSN": ["0028-0836", "1476-4687"]}

    with patch.object(searcher.crossref, 'get_journal_by_issn', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_journal

        resolved = await searcher._resolve_journal_filter(filter_obj)

        # High similarity, should be verified
        assert resolved._resolution_verified is True

    await searcher.close()


@pytest.mark.asyncio
async def test_search_with_single_source_crossref(config, mock_crossref_results):
    """Test search with single source (crossref only)."""
    searcher = WebSearcher(config)

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        mock_cr.return_value = mock_crossref_results

        results = await searcher.search("test query", sources=["crossref"])

        # Only crossref should be used
        assert results.sources_used == ["crossref"]
        assert len(results.results) == len(mock_crossref_results)

    await searcher.close()


@pytest.mark.asyncio
async def test_search_with_single_source_s2(config, mock_s2_results):
    """Test search with single source (s2 only)."""
    searcher = WebSearcher(config)

    with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
        mock_s2.return_value = mock_s2_results

        results = await searcher.search("test query", sources=["s2"])

        # Only s2 should be used
        assert results.sources_used == ["s2"]

    await searcher.close()


@pytest.mark.asyncio
async def test_search_with_invalid_source(config):
    """Test search with invalid source name (should be ignored)."""
    searcher = WebSearcher(config)

    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as mock_cr:
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as mock_s2:
            mock_cr.return_value = []
            mock_s2.return_value = []

            # Invalid source should be ignored, no sources used
            results = await searcher.search("test query", sources=["invalid_source"])

            # No valid sources, so no results
            assert len(results.sources_used) == 0
            assert len(results.results) == 0

    await searcher.close()


def test_parse_bibtex():
    """Test BibTeX parsing."""
    bibtex = """@article{chen2022private,
  title={Private communication and management forecasts: Evidence from corporate site visits},
  author={Chen, Xiaoqi and Cheng, CS Agnes and Xie, Jing and Yang, Haoyi},
  journal={Corporate Governance: An International Review},
  volume={30},
  number={4},
  pages={482--497},
  year={2022},
  publisher={Wiley Online Library}
}"""

    result = parse_bibtex(bibtex)

    assert result["entry_type"] == "article"
    assert result["citekey"] == "chen2022private"
    assert result["title"] == "Private communication and management forecasts: Evidence from corporate site visits"
    assert len(result["author"]) == 4
    assert result["author"][0] == "Chen, Xiaoqi"
    assert result["journal"] == "Corporate Governance: An International Review"
    assert result["year"] == 2022
    assert result["volume"] == "30"
    assert result["number"] == "4"
    assert result["pages"] == "482--497"
    assert result["publisher"] == "Wiley Online Library"