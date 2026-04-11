"""Tests for metadata extraction."""

import pytest

from libby.config.loader import load_config
from libby.core.metadata import MetadataExtractor, MetadataNotFoundError


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