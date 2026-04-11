"""Retry utilities for API calls."""

import asyncio
from typing import Callable, Any

from libby.models.config import RetryConfig


async def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs,
) -> Any:
    """Execute function with exponential backoff retry.

    Args:
        func: Async function to execute.
        config: Retry configuration.
        *args, **kwargs: Arguments to pass to func.

    Returns:
        Result of func if successful.

    Raises:
        Last exception if all retries fail.
    """
    last_exception = None
    delays = config.delays

    for attempt in range(len(delays) + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < len(delays):
                await asyncio.sleep(delays[attempt])
            else:
                break

    raise last_exception