"""Google Scholar search wrapper using scholarly package."""

import asyncio
from typing import Optional

from scholarly import scholarly
from libby.models.search_filter import SearchFilter


class ScholarlyAPI:
    """Google Scholar search via scholarly package.

    Note: scholarly is a sync library, wrapped in async executor.
    May trigger Google anti-bot, use conservative rate limit.
    """

    async def search(
        self,
        query: str,
        limit: int = 50,
        filter: SearchFilter | None = None,
    ) -> list[dict]:
        """Search Google Scholar.

        Converts SearchFilter to query keywords:
        - year_from/year_to: "after:{year}", "before:{year}"
        - venue: "source:{venue}"

        Args:
            query: Search keywords
            limit: Result count
            filter: Unified SearchFilter

        Returns:
            Raw result list from scholarly
        """
        if filter is None:
            filter = SearchFilter()

        # Enhance query with filter keywords
        enhanced_query = query

        if filter.year_from:
            enhanced_query += f" after:{filter.year_from}"
        if filter.year_to:
            enhanced_query += f" before:{filter.year_to}"
        if filter.venue:
            enhanced_query += f" source:{filter.venue}"

        def _sync_search():
            """Sync search in thread."""
            results = []
            try:
                search_gen = scholarly.search_pubs(enhanced_query)
                for i, result in enumerate(search_gen):
                    if i >= limit:
                        break
                    results.append(result)
            except Exception:
                # Handle anti-bot or network errors gracefully
                pass
            return results

        # Run in thread pool (scholarly is sync)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_search)

    async def close(self):
        """Close any resources (no session needed for scholarly)."""
        pass