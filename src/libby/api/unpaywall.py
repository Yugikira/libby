"""Unpaywall API client."""

from libby.api.base import AsyncAPIClient, RateLimit


class UnpaywallAPI(AsyncAPIClient):
    """Unpaywall API for open-access PDF lookup."""

    RATE_LIMIT = RateLimit(1, 1)  # 1 req/sec
    BASE_URL = "https://api.unpaywall.org/v2"

    async def get_pdf_url(self, doi: str, email: str) -> tuple[str | None, dict]:
        """Get best OA PDF URL from Unpaywall.

        Args:
            doi: DOI to look up
            email: Email address for Unpaywall (required)

        Returns:
            (pdf_url, metadata) or (None, {}) if not found
        """
        url = f"{self.BASE_URL}/{doi}?email={email}"

        data = await self.get(url)

        if data.get("status") == "error":
            return None, {}

        best_oa = data.get("best_oa_location")
        if best_oa and best_oa.get("url_for_pdf"):
            pdf_url = best_oa["url_for_pdf"]
            meta = {
                "title": data.get("title"),
                "year": data.get("year"),
            }
            return pdf_url, meta

        return None, {}
