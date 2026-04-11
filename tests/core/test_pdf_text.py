"""Tests for PDF text extraction."""

from pathlib import Path

import pytest

from libby.core.pdf_text import extract_first_page_text


def test_extract_first_page(example_pdf_path):
    """Test extracting text from first page."""
    text = extract_first_page_text(example_pdf_path)
    assert isinstance(text, str)
    # Should contain some text (not empty for valid PDF)


def test_extract_nonexistent_pdf():
    """Test extracting from nonexistent file."""
    result = extract_first_page_text(Path("/nonexistent/file.pdf"))
    assert result == ""