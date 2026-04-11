"""Tests for AI extractor."""

import os
import pytest

from libby.config.loader import load_config
from libby.core.ai_extractor import AIExtractor


@pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY not set")
@pytest.mark.asyncio
async def test_ai_extract():
    """Test AI extraction (requires API key)."""
    config = load_config(config_path=None)
    extractor = AIExtractor(config)

    sample_text = """Journal of Accounting Research
DOI: 10.1007/s11142-016-9368-9

Earnings Management Consequences of Cross-Listing

Abstract: This paper examines..."""

    result = await extractor.extract_from_text(sample_text)
    assert "doi" in result
    assert "title" in result


def test_ai_extractor_requires_api_key():
    """Test that AIExtractor raises error without API key."""
    from libby.models.config import LibbyConfig, AIExtractorConfig

    config = LibbyConfig(ai_extractor=AIExtractorConfig(api_key=None))

    # Clear environment variable for this test
    old_key = os.environ.pop("DEEPSEEK_API_KEY", None)

    try:
        with pytest.raises(ValueError, match="requires api_key"):
            AIExtractor(config)
    finally:
        # Restore if existed
        if old_key:
            os.environ["DEEPSEEK_API_KEY"] = old_key