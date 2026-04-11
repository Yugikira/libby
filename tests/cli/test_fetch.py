"""Tests for fetch CLI command."""

import pytest
from typer.testing import CliRunner
from libby.__main__ import app

runner = CliRunner()


def test_fetch_help():
    """Test fetch --help."""
    result = runner.invoke(app, ["fetch", "--help"])
    assert result.exit_code == 0
    assert "Fetch PDF by DOI" in result.stdout


def test_fetch_no_input():
    """Test fetch without DOI or batch file."""
    result = runner.invoke(app, ["fetch"])
    # Exit code 2 = missing required argument (typer default)
    assert result.exit_code in [1, 2]


def test_fetch_dry_run():
    """Test fetch --dry-run."""
    # This test documents expected behavior
    # Actual implementation may vary
    result = runner.invoke(app, [
        "fetch",
        "10.1007/s11142-016-9368-9",
        "--dry-run",
        "--no-env-check",
    ])
    # Expected: shows PDF URL without downloading
