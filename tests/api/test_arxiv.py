"""Tests for arXiv URL builder."""

from libby.api.arxiv import ArxivAPI


def test_get_pdf_url_modern_id():
    """Test modern arXiv ID format."""
    url = ArxivAPI.get_pdf_url("2301.12345")
    assert url == "https://arxiv.org/pdf/2301.12345.pdf"


def test_get_pdf_url_old_format():
    """Test old arXiv ID format."""
    url = ArxivAPI.get_pdf_url("hep-th/9901001")
    assert url == "https://arxiv.org/pdf/hep-th/9901001.pdf"


def test_get_pdf_url_with_prefix():
    """Test ID with arXiv: prefix."""
    url = ArxivAPI.get_pdf_url("arXiv:2301.12345")
    assert url == "https://arxiv.org/pdf/2301.12345.pdf"
