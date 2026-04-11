"""Integration tests for extract command."""

import subprocess
from pathlib import Path


def test_extract_doi():
    """Test extracting metadata from DOI via CLI."""
    result = subprocess.run(
        ["uv", "run", "libby", "extract", "10.1007/s11142-016-9368-9", "--no-env-check"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    assert result.returncode == 0
    # Check output contains expected fields
    assert "author" in result.stdout.lower() or "stent" in result.stdout.lower()


def test_extract_help():
    """Test help command."""
    result = subprocess.run(
        ["uv", "run", "libby", "extract", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    assert result.returncode == 0
    assert "DOI" in result.stdout or "doi" in result.stdout


def test_main_help():
    """Test main CLI help."""
    result = subprocess.run(
        ["uv", "run", "libby", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )
    assert result.returncode == 0
    assert "libby" in result.stdout.lower()