"""Serpapi Google Scholar client."""

from libby.api.base import AsyncAPIClient, RateLimit
from libby.models.search_filter import SearchFilter


class SerpapiConfirmationNeeded(Exception):
    """Raised when Serpapi confirmation is needed.

    All free sources failed, user must confirm API usage.
    """

    def __init__(self, doi: str):
        self.doi = doi
        self.message = (
            "All free sources failed to find PDF.\n"
            "Serpapi Google Scholar is available but uses API quota.\n"
            "Do you want to try Serpapi? (y/n)"
        )


class SerpapiAPI(AsyncAPIClient):
    """Serpapi Google Scholar API."""

    RATE_LIMIT = RateLimit(1, 5)  # 1 req per 5 seconds
    BASE_URL = "https://serpapi.com/search"

    async def get_pdf_url(self, doi: str, api_key: str) -> str | None:
        """Search Google Scholar for PDF link via Serpapi.

        Args:
            doi: DOI to search
            api_key: Serpapi API key

        Returns:
            PDF URL or None if not found
        """
        params = {
            "engine": "google_scholar",
            "q": doi,
            "api_key": api_key,
        }

        data = await self.get(self.BASE_URL, params=params)

        if not data or "error" in data:
            return None

        # Search organic results for PDF links
        for result in data.get("organic_results", []):
            link = result.get("link", "")
            if link.endswith(".pdf"):
                return link

            # Check for PDF resource
            resources = result.get("resources", [])
            for res in resources:
                if res.get("file_format") == "PDF":
                    return res.get("link")

        return None

    async def search(
        self,
        query: str,
        api_key: str,
        max_pages: int = 5,
        filter: SearchFilter | None = None,
    ) -> tuple[list[dict], bool]:
        """Search Google Scholar via Serpapi.

        Controlled API usage:
        - Max 5 pages per search (50 results)
        - Retry on failure (max 2 per page)

        Filter support:
        - author: Added as "author:{name}" in query
        - venue: Added as "source:{venue}" in query
        - year_from/year_to: Use as_ylo/as_yhi parameters

        Args:
            query: Search keywords
            api_key: Serpapi API key
            max_pages: Max pages to fetch
            filter: SearchFilter for author, venue, year filtering

        Returns:
            (results, quota_reached)
            quota_reached=True means skip Serpapi
        """
        all_results: list[dict] = []
        quota_reached = False

        # Build enhanced query with author and venue
        enhanced_query = query
        if filter:
            # Author: embed in query
            if filter.author:
                enhanced_query += f" author:{filter.author}"
            # Venue: use resolved venue if available
            venue = filter._resolved_venue or filter.venue
            if venue:
                enhanced_query += f" source:{venue}"

        for page in range(max_pages):
            params = {
                "engine": "google_scholar",
                "q": enhanced_query,
                "api_key": api_key,
                "num": 10,
                "start": page * 10,
            }

            # Year range: use dedicated parameters
            if filter:
                if filter.year_from:
                    params["as_ylo"] = filter.year_from
                if filter.year_to:
                    params["as_yhi"] = filter.year_to

            # Retry up to 2 times per page
            for attempt in range(2):
                try:
                    data = await self.get(self.BASE_URL, params=params)

                    # Check for quota errors
                    if data and "error" in data:
                        error_msg = data["error"].lower()
                        if "quota" in error_msg or "invalid api key" in error_msg:
                            return all_results, True

                    # No data or other error, continue to next page
                    if not data:
                        break

                    # Extract organic results
                    organic_results = data.get("organic_results", [])
                    all_results.extend(organic_results)
                    break

                except Exception:
                    # On exception, retry if attempts remaining
                    if attempt == 1:
                        # Max retries reached, continue to next page
                        break
                    continue

        return all_results, quota_reached
