"""Async HTTP client base with rate limiting."""

import asyncio
from typing import Optional

import aiohttp
from aiolimiter import AsyncLimiter


class RateLimit:
    """Rate limit configuration."""

    def __init__(self, requests: int, period: int):
        self.requests = requests
        self.period = period


class AsyncAPIClient:
    """Async HTTP client with rate limit control."""

    RATE_LIMIT = RateLimit(1, 1)  # Default: 1 req/sec

    def __init__(self):
        self._limiter = AsyncLimiter(
            self.RATE_LIMIT.requests,
            self.RATE_LIMIT.period,
        )
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get(self, url: str, **kwargs) -> dict:
        """Make GET request with rate limiting."""
        await self._limiter.acquire()
        session = await self._get_session()

        async with session.get(url, **kwargs) as resp:
            if resp.status == 429:
                # Rate limited - wait and retry once
                await asyncio.sleep(5)
                async with session.get(url, **kwargs) as retry_resp:
                    return await retry_resp.json()
            return await resp.json()

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()