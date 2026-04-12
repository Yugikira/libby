"""Tests for websearch CLI command."""

import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, MagicMock, patch
import json

from libby.__main__ import app

runner = CliRunner()


def test_websearch_help():
    """Test websearch --help shows usage."""
    result = runner.invoke(app, ["websearch", "--help"])
    assert result.exit_code == 0
    assert "Search academic databases" in result.stdout
    assert "--output" in result.stdout
    assert "--format" in result.stdout
    assert "--limit" in result.stdout
    assert "--year-from" in result.stdout
    assert "--venue" in result.stdout


def test_websearch_no_query():
    """Test websearch without query shows error."""
    result = runner.invoke(app, ["websearch"])
    # Exit code 2 = missing required argument (typer default)
    assert result.exit_code in [1, 2]
    assert "No input provided" in result.stdout or "Missing argument" in result.stdout


def test_websearch_doi_fallback():
    """Test DOI input triggers fetch workflow."""
    doi = "10.1007/s11142-016-9368-9"

    # Mock the fetch and extract workflow
    with patch("libby.cli.websearch.is_doi", return_value=True):
        with patch("libby.cli.websearch.MetadataExtractor") as mock_extractor_cls:
            with patch("libby.cli.websearch.PDFFetcher") as mock_fetcher_cls:
                # Setup mocks
                mock_extractor = MagicMock()
                mock_extractor.extract_from_doi = AsyncMock(return_value=MagicMock(
                    citekey="huang_2016_disclosure",
                    title="Disclosure",
                    author=["Huang"],
                    year=2016,
                    doi=doi,
                    to_dict=lambda: {"citekey": "huang_2016_disclosure", "doi": doi}
                ))
                mock_extractor.close = AsyncMock()
                mock_extractor_cls.return_value = mock_extractor

                mock_fetcher = MagicMock()
                mock_fetcher.fetch = AsyncMock(return_value=MagicMock(
                    success=False,
                    error="All sources failed"
                ))
                mock_fetcher.close = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher

                result = runner.invoke(app, [
                    "websearch",
                    doi,
                    "--no-env-check",
                ])

                # DOI fallback should trigger metadata extraction
                assert mock_extractor.extract_from_doi.called


def test_websearch_filter_options():
    """Test filter options are passed to WebSearcher."""
    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=MagicMock(
            query="machine learning",
            results=[],
            serpapi_extra=[],
            total_count=0,
            sources_used=["crossref"],
            to_bibtex=lambda config: "",
            to_json=lambda: json.dumps({"query": "machine learning", "results": []}),
        ))
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        result = runner.invoke(app, [
            "websearch",
            "machine learning",
            "--year-from", "2020",
            "--year-to", "2023",
            "--venue", "Nature",
            "--issn", "1234-5678",
            "--limit", "20",
            "--no-env-check",
        ])

        assert result.exit_code == 0
        # Verify search was called with correct parameters
        assert mock_searcher.search.called
        call_args = mock_searcher.search.call_args
        assert call_args[0][0] == "machine learning"  # query
        # Check kwargs
        assert call_args[1]["limit"] == 20


def test_websearch_output_bibtex():
    """Test --format bibtex output."""
    from libby.models.search_result import SearchResult, SearchResults
    from libby.models.config import CitekeyConfig

    mock_results = SearchResults(
        query="test query",
        results=[
            SearchResult(
                doi="10.1234/test",
                title="Test Paper",
                author=["Test Author"],
                year=2023,
                journal="Test Journal",
            )
        ],
        total_count=1,
        sources_used=["crossref"],
    )

    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=mock_results)
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        result = runner.invoke(app, [
            "websearch",
            "test query",
            "--format", "bibtex",
            "--no-env-check",
        ])

        assert result.exit_code == 0
        # BibTeX output should contain citekey
        assert "10.1234/test" in result.stdout or "Test Paper" in result.stdout


def test_websearch_output_json():
    """Test --format json output."""
    from libby.models.search_result import SearchResult, SearchResults

    mock_results = SearchResults(
        query="test query",
        results=[
            SearchResult(
                doi="10.1234/test",
                title="Test Paper",
                author=["Test Author"],
                year=2023,
            )
        ],
        total_count=1,
        sources_used=["crossref"],
    )

    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=mock_results)
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        result = runner.invoke(app, [
            "websearch",
            "test query",
            "--format", "json",
            "--no-env-check",
        ])

        assert result.exit_code == 0
        # JSON output should be parseable
        # Output includes rich table, find JSON section
        assert "test query" in result.stdout


def test_websearch_output_file():
    """Test --output saves to file."""
    import tempfile
    from pathlib import Path
    from libby.models.search_result import SearchResult, SearchResults

    mock_results = SearchResults(
        query="test query",
        results=[
            SearchResult(
                doi="10.1234/test",
                title="Test Paper",
                author=["Test Author"],
                year=2023,
            )
        ],
        total_count=1,
        sources_used=["crossref"],
    )

    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=mock_results)
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "results.bib"

            result = runner.invoke(app, [
                "websearch",
                "test query",
                "--output", str(output_file),
                "--no-env-check",
            ])

            assert result.exit_code == 0
            assert output_file.exists()
            content = output_file.read_text()
            assert "10.1234/test" in content


def test_websearch_no_serpapi():
    """Test --no-serpapi skips Serpapi search."""
    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=MagicMock(
            query="test",
            results=[],
            to_bibtex=lambda config: "",
            to_json=lambda: "{}",
            total_count=0,
            sources_used=["crossref"],
        ))
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        result = runner.invoke(app, [
            "websearch",
            "test query",
            "--no-serpapi",
            "--no-env-check",
        ])

        assert result.exit_code == 0
        # Verify skip_serpapi was passed
        call_args = mock_searcher.search.call_args
        assert call_args[1]["skip_serpapi"] is True


def test_websearch_display_table():
    """Test results displayed in rich Table format."""
    from libby.models.search_result import SearchResult, SearchResults

    mock_results = SearchResults(
        query="test query",
        results=[
            SearchResult(
                doi="10.1234/test",
                title="Test Paper",
                author=["Test Author"],
                year=2023,
                journal="Test Journal",
            ),
            SearchResult(
                doi="10.5678/another",
                title="Another Paper",
                author=["Another Author"],
                year=2022,
                journal="Another Journal",
            ),
        ],
        total_count=2,
        sources_used=["crossref", "semantic_scholar"],
    )

    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=mock_results)
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        result = runner.invoke(app, [
            "websearch",
            "test query",
            "--no-env-check",
        ])

        assert result.exit_code == 0
        # Table should show key fields
        assert "Test Paper" in result.stdout
        assert "Test Author" in result.stdout
        # Results count shown
        assert "2" in result.stdout


def test_websearch_empty_results():
    """Test handling of empty results."""
    from libby.models.search_result import SearchResults

    mock_results = SearchResults(
        query="obscure query",
        results=[],
        total_count=0,
        sources_used=["crossref"],
    )

    with patch("libby.cli.websearch.WebSearcher") as mock_searcher_cls:
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(return_value=mock_results)
        mock_searcher.close = AsyncMock()
        mock_searcher_cls.return_value = mock_searcher

        result = runner.invoke(app, [
            "websearch",
            "obscure query",
            "--no-env-check",
        ])

        assert result.exit_code == 0
        assert "No results" in result.stdout or "0" in result.stdout