"""Tests for is_doi function."""

from libby.utils.doi_parser import is_doi


def test_is_doi_direct():
    """Test direct DOI format."""
    assert is_doi("10.1007/s11142-016-9368-9") is True
    assert is_doi("10.1038/nature12373") is True


def test_is_doi_url_format():
    """Test URL-format DOI."""
    assert is_doi("https://doi.org/10.1007/s11142-016-9368-9") is True
    assert is_doi("http://doi.org/10.1038/nature12373") is True
    assert is_doi("doi.org/10.1038/nature12373") is True


def test_is_doi_with_prefix():
    """Test DOI with prefix."""
    assert is_doi("DOI:10.1007/s11142-016-9368-9") is True
    assert is_doi("doi:10.1038/nature12373") is True
    assert is_doi("DOI 10.1007/s11142-016-9368-9") is True


def test_is_doi_other_registrants():
    """Test DOI from other registrant agencies (not Crossref)."""
    # mEDRA (European DOI registrar)
    assert is_doi("m2.123/abc456") is True
    assert is_doi("https://doi.org/m2.123/abc456") is True
    # CNKI (Chinese DOI registrar)
    assert is_doi("10a.123/xyz") is True


def test_is_doi_title():
    """Test non-DOI strings (titles)."""
    assert is_doi("corporate site visit") is False
    assert is_doi("Capital market effects of media synthesis") is False
    assert is_doi("10") is False  # Not a valid DOI
    assert is_doi("10.123") is False  # Missing suffix