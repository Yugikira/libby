"""Tests for DOI parsing."""

import pytest

from libby.utils.doi_parser import normalize_doi, extract_doi_from_text


def test_normalize_doi_plain():
    """Test normalizing plain DOI."""
    assert normalize_doi("10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"


def test_normalize_doi_with_prefix():
    """Test normalizing DOI with various prefixes."""
    assert normalize_doi("https://doi.org/10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"
    assert normalize_doi("doi.org/10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"
    assert normalize_doi("DOI:10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"
    assert normalize_doi("doi:10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"


def test_normalize_doi_lowercase():
    """Test DOI is lowercased."""
    assert normalize_doi("10.1007/ABC-123") == "10.1007/abc-123"


def test_extract_doi_direct():
    """Test extracting DOI with direct match."""
    text = "This paper DOI: 10.1007/s11142-016-9368-9 was published"
    assert extract_doi_from_text(text) == "10.1007/s11142-016-9368-9"


def test_extract_doi_hyphen_break():
    """Test extracting DOI with hyphen line break."""
    text = "DOI: 10.1007/s11142-\n016-9368-9"
    assert extract_doi_from_text(text) == "10.1007/s11142-016-9368-9"


def test_extract_doi_no_match():
    """Test when no DOI present."""
    text = "This is just plain text without any DOI"
    assert extract_doi_from_text(text) is None