"""Tests for API base client."""

import pytest

from libby.api.base import AsyncAPIClient, RateLimit


def test_rate_limit_creation():
    """Test RateLimit configuration."""
    rl = RateLimit(10, 60)
    assert rl.requests == 10
    assert rl.period == 60


def test_client_creation():
    """Test client initialization."""
    client = AsyncAPIClient()
    assert client._limiter is not None


@pytest.mark.asyncio
async def test_client_close():
    """Test closing client."""
    client = AsyncAPIClient()
    await client.close()