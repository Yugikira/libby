"""Pytest fixtures."""

from pathlib import Path
import pytest


@pytest.fixture
def example_pdf_path() -> Path:
    """Path to example test PDF."""
    return Path(__file__).parent / "example" / "test.pdf"