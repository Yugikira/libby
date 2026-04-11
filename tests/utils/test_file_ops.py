"""Tests for FileHandler."""

import pytest
from pathlib import Path
from libby.utils.file_ops import FileHandler
from libby.models.metadata import BibTeXMetadata


def test_organize_pdf_bytes(tmp_path):
    """Test organizing PDF from bytes."""
    handler = FileHandler(tmp_path)

    # Create mock PDF bytes
    pdf_bytes = b"%PDF-1.4 mock pdf content"

    metadata = BibTeXMetadata(
        citekey="test_2023_paper",
        entry_type="article",
        author=["Test, Author"],
        title="Test Paper",
        year=2023,
        doi="10.1234/test",
    )

    result_dir = handler.organize_pdf_bytes(pdf_bytes, metadata)

    assert result_dir == tmp_path / "test_2023_paper"
    assert (result_dir / "test_2023_paper.pdf").exists()
    assert (result_dir / "test_2023_paper.bib").exists()
