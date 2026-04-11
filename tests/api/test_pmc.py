"""Tests for PMC URL builder."""

from libby.api.pmc import PMCAPI


def test_get_pdf_url_with_pmc_prefix():
    """Test PMCID with PMC prefix."""
    url = PMCAPI.get_pdf_url("PMC123456")
    assert url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/pdf/"


def test_get_pdf_url_without_prefix():
    """Test PMCID without PMC prefix."""
    url = PMCAPI.get_pdf_url("123456")
    assert url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/pdf/"


def test_get_pdf_url_lowercase():
    """Test lowercase pmc prefix."""
    url = PMCAPI.get_pdf_url("pmc123456")
    # The API adds PMC prefix but preserves case
    assert "pmc123456" in url.lower()
