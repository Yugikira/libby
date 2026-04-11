"""Serpapi Google Scholar client."""

from libby.api.base import AsyncAPIClient, RateLimit


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
