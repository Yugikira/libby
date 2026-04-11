"""Tests for citekey formatting."""

import pytest

from libby.config.loader import load_config
from libby.core.citekey import CitekeyFormatter
from libby.models.metadata import BibTeXMetadata


def test_format_default():
    """Test default citekey format."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=["Stent, Angela", "Yang, Kaitlin"],
        title="Earnings Management Consequences of Cross-Listing",
        year=2016,
    )

    citekey = formatter.format(metadata)
    assert citekey == "stent_2016_earnings_management_consequences"


def test_format_multiple_authors():
    """Test with multiple authors - only first is used."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=["Smith, John", "Jones, Jane"],
        title="Test Paper",
        year=2020,
    )

    citekey = formatter.format(metadata)
    assert citekey.startswith("smith_")


def test_format_no_author():
    """Test with no author."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=[],
        title="Test Paper",
        year=2020,
    )

    citekey = formatter.format(metadata)
    assert citekey.startswith("unknown_")


def test_format_ignored_words():
    """Test that ignored words are filtered."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=["Test"],
        title="The Quick Brown Fox",
        year=2020,
    )

    citekey = formatter.format(metadata)
    assert "the" not in citekey
    assert "quick" in citekey