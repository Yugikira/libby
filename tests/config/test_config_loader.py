"""Tests for configuration loading."""

import os
from pathlib import Path
import tempfile

import pytest

from libby.config.loader import load_config
from libby.models.config import LibbyConfig


def test_load_default_config():
    """Test loading default config when no file exists."""
    config = load_config(config_path=Path("/nonexistent/config.yaml"))
    assert config.papers_dir == Path.home() / ".lib" / "papers"
    assert config.citekey.pattern == "{author}_{year}_{title}"
    assert config.citekey.author_words == 1
    assert config.citekey.title_words == 3


def test_load_custom_config():
    """Test loading custom config file.

    Note: papers_dir is derived from lib_dir, not a direct config field.
    The config uses 'lib_dir' as base, with auto-generated subdirectories.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write("""
lib_dir: /custom/lib
citekey:
  author_words: 2
  title_words: 5
""")
        temp_path = Path(f.name)

    try:
        config = load_config(config_path=temp_path)
        # papers_dir is derived from lib_dir
        assert config.papers_dir == Path("/custom/lib/papers")
        assert config.citekey.author_words == 2
        assert config.citekey.title_words == 5
    finally:
        temp_path.unlink()


def test_env_var_priority():
    """Test environment variable override."""
    os.environ["LIBBY_CONFIG"] = "/env/config.yaml"
    # This would be tested with mock file
    del os.environ["LIBBY_CONFIG"]