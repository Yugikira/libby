"""Google Scholar search wrapper using scholarly package."""

import asyncio
import logging
from typing import Optional

from scholarly import scholarly
from libby.models.search_filter import SearchFilter

logger = logging.getLogger(__name__)


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
        - author: "author:{name}"

        Args:
            query: Search keywords
            limit: Result count
            filter: Unified SearchFilter (default: year_from = current_year - 2)

        Returns:
            Raw result list from scholarly
        """
        # Create default filter with year_from = current_year - 2
        if filter is None:
            from datetime import datetime
            filter = SearchFilter(year_from=datetime.now().year - 2)

        # Enhance query with filter keywords
        enhanced_query = query

        # Author: embed in query
        if filter.author:
            enhanced_query += f" author:{filter.author}"

        # Venue: use resolved venue if available
        venue = filter._resolved_venue or filter.venue
        if venue:
            enhanced_query += f" source:{venue}"

        if filter.year_from:
            enhanced_query += f" after:{filter.year_from}"
        if filter.year_to:
            enhanced_query += f" before:{filter.year_to}"

        def _sync_search():
            """Sync search in thread."""
            results = []
            try:
                search_gen = scholarly.search_pubs(enhanced_query)
                for i, result in enumerate(search_gen):
                    if i >= limit:
                        break
                    results.append(result)
            except Exception as e:
                # Handle anti-bot or network errors gracefully
                logger.warning(f"Scholarly search failed: {e}")
                pass
            return results

        # Run in thread pool (scholarly is sync)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_search)

    async def close(self):
        """Close any resources (no session needed for scholarly)."""
        pass