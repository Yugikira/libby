"""Tests for LibbyConfig."""

from libby.models.config import LibbyConfig


def test_libby_config_fetch_defaults():
    """Test default fetch configuration."""
    config = LibbyConfig()

    assert config.scihub_url == "https://sci-hub.ru"
    assert config.pdf_max_size == 50 * 1024 * 1024  # 50 MB
