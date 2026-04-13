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
        self._session_lock = asyncio.Lock()  # Prevent race condition in session creation

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session with lock to prevent race conditions."""
        if self._session is None or self._session.closed:
            async with self._session_lock:
                # Double-check after acquiring lock
                if self._session is None or self._session.closed:
                    timeout = aiohttp.ClientTimeout(total=60, connect=10)
                    self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def get(self, url: str, **kwargs) -> dict:
        """Make GET request with rate limiting and proper error handling."""
        await self._limiter.acquire()
        session = await self._get_session()

        try:
            async with session.get(url, **kwargs) as resp:
                if resp.status == 429:
                    # Rate limited - wait and retry once (same session, no nested context)
                    await asyncio.sleep(5)
                    await self._limiter.acquire()  # Acquire again for retry
                    async with session.get(url, **kwargs) as retry_resp:
                        if retry_resp.status == 404:
                            return {"status": "not_found"}
                        if retry_resp.status >= 500:
                            return {"status": "error", "code": retry_resp.status}
                        return await retry_resp.json()
                if resp.status == 404:
                    return {"status": "not_found"}
                if resp.status >= 500:
                    return {"status": "error", "code": resp.status}
                return await resp.json()
        except aiohttp.ClientError as e:
            return {"status": "error", "message": str(e)}

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()