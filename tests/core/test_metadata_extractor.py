"""Tests for metadata extraction."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from libby.config.loader import load_config
from libby.core.metadata import MetadataExtractor, MetadataNotFoundError
from libby.models.metadata import BibTeXMetadata


@pytest.mark.asyncio
async def test_extract_from_doi():
    """Test extracting metadata from DOI."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    doi = "10.1007/s11142-016-9368-9"
    metadata = await extractor.extract_from_doi(doi)

    assert metadata.doi == doi
    assert metadata.citekey is not None
    assert metadata.year is not None

    await extractor.close()


@pytest.mark.asyncio
async def test_extract_not_found():
    """Test when DOI is not found."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    with pytest.raises(MetadataNotFoundError):
        await extractor.extract_from_doi("10.0000/invalid-doi")

    await extractor.close()


@pytest.mark.asyncio
async def test_ai_doi_verification_fallback():
    """Test that AI-extracted DOI with mismatched title falls back to title search."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    # Create mock PDF path
    mock_pdf = Path("/fake/test.pdf")

    # Mock extract_first_page_text to return sample text
    with patch("libby.core.metadata.extract_first_page_text", return_value="sample text"):
        # Mock _ai_extract to return hallucinated DOI with real title
        ai_result = {
            "doi": "10.1234/hallucinated-doi",  # Fake DOI
            "title": "Earnings Management Consequences of Cross-Listing"  # Real title
        }

        # Mock extract_from_doi to return mismatched metadata (different paper)
        wrong_metadata = BibTeXMetadata(
            citekey="smith_2020_different_paper",
            doi="10.1234/hallucinated-doi",
            title="A Completely Different Paper Title About Something Else",
            author=["Smith, John"],
            year=2020,
        )

        # Mock extract_from_title to return correct metadata
        correct_metadata = BibTeXMetadata(
            citekey="chen_2016_earnings_management",
            doi="10.1007/s11142-016-9368-9",
            title="Earnings Management Consequences of Cross-Listing",
            author=["Chen, Shuping", "Huang, Yining", "Li, Ningzhong"],
            year=2016,
        )

        # Set up mocks
        extractor._ai_extract = AsyncMock(return_value=ai_result)
        extractor.extract_from_doi = AsyncMock(return_value=wrong_metadata)
        extractor.extract_from_title = AsyncMock(return_value=correct_metadata)

        # Run extraction
        result = await extractor.extract_from_pdf(mock_pdf, use_ai=True)

        # Verify fallback occurred - extract_from_title should be called
        extractor.extract_from_title.assert_called_once_with("Earnings Management Consequences of Cross-Listing")

        # Result should be the correct metadata from title search
        assert result.doi == "10.1007/s11142-016-9368-9"
        assert result.title == "Earnings Management Consequences of Cross-Listing"

    await extractor.close()


@pytest.mark.asyncio
async def test_ai_doi_verification_pass():
    """Test that AI-extracted DOI with matching title proceeds normally."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    mock_pdf = Path("/fake/test.pdf")

    with patch("libby.core.metadata.extract_first_page_text", return_value="sample text"):
        # AI returns correct DOI and title
        ai_result = {
            "doi": "10.1007/s11142-016-9368-9",
            "title": "Earnings Management Consequences of Cross-Listing"
        }

        # Crossref returns matching metadata (similar title - slightly different punctuation)
        matching_metadata = BibTeXMetadata(
            citekey="chen_2016_earnings_management",
            doi="10.1007/s11142-016-9368-9",
            title="Earnings Management Consequences of Cross-Listing",  # Exact match
            author=["Chen, Shuping", "Huang, Yining", "Li, Ningzhong"],
            year=2016,
        )

        extractor._ai_extract = AsyncMock(return_value=ai_result)
        extractor.extract_from_doi = AsyncMock(return_value=matching_metadata)
        extractor.extract_from_title = AsyncMock()  # Should NOT be called

        result = await extractor.extract_from_pdf(mock_pdf, use_ai=True)

        # extract_from_title should NOT be called (title matches)
        extractor.extract_from_title.assert_not_called()

        # Result should be from extract_from_doi
        assert result.doi == "10.1007/s11142-016-9368-9"

    await extractor.close()


@pytest.mark.asyncio
async def test_ai_doi_no_title_skip_verification():
    """Test that AI-extracted DOI without title skips verification."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    mock_pdf = Path("/fake/test.pdf")

    with patch("libby.core.metadata.extract_first_page_text", return_value="sample text"):
        # AI returns DOI but no title
        ai_result = {
            "doi": "10.1007/s11142-016-9368-9",
            "title": None
        }

        metadata = BibTeXMetadata(
            citekey="chen_2016_earnings_management",
            doi="10.1007/s11142-016-9368-9",
            title="Earnings Management Consequences of Cross-Listing",
            author=["Chen, Shuping"],
            year=2016,
        )

        extractor._ai_extract = AsyncMock(return_value=ai_result)
        extractor.extract_from_doi = AsyncMock(return_value=metadata)
        extractor.extract_from_title = AsyncMock()

        result = await extractor.extract_from_pdf(mock_pdf, use_ai=True)

        # Should proceed without calling extract_from_title (no AI title to verify)
        extractor.extract_from_title.assert_not_called()
        assert result.doi == "10.1007/s11142-016-9368-9"

    await extractor.close()