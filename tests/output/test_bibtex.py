"""Tests for BibTeX output."""

import json

from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter
from libby.models.metadata import BibTeXMetadata


def test_bibtex_single_entry():
    """Test formatting single BibTeX entry."""
    formatter = BibTeXFormatter()
    metadata = BibTeXMetadata(
        citekey="stent_2016_earnings",
        entry_type="article",
        author=["Stent, Angela"],
        title="Earnings Management",
        year=2016,
        doi="10.1007/s11142-016-9368-9",
    )

    output = formatter.format(metadata)
    assert "@article{stent_2016_earnings," in output
    assert "author = {Stent, Angela}" in output
    assert "doi = {10.1007/s11142-016-9368-9}" in output


def test_bibtex_multiple_entries():
    """Test formatting multiple BibTeX entries."""
    formatter = BibTeXFormatter()
    metadata_list = [
        BibTeXMetadata(citekey="a", author=["Author A"], title="A", year=2020),
        BibTeXMetadata(citekey="b", author=["Author B"], title="B", year=2021),
    ]

    output = formatter.format_batch(metadata_list)
    assert "@article{a," in output
    assert "@article{b," in output


def test_json_single_entry():
    """Test formatting single JSON entry."""
    formatter = JSONFormatter()
    metadata = BibTeXMetadata(
        citekey="test_2024_paper",
        title="Test",
        year=2024,
    )

    output = formatter.format(metadata)
    data = json.loads(output)
    assert data["citekey"] == "test_2024_paper"