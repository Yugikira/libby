"""Semantic Scholar API client."""

from libby.api.base import AsyncAPIClient, RateLimit


class SemanticScholarAPI(AsyncAPIClient):
    """Semantic Scholar API for paper metadata and OA PDFs."""

    RATE_LIMIT = RateLimit(1, 1)  # Always 1 req/sec, even with API key
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.api_key = api_key

    async def get_pdf_url(self, doi: str) -> tuple[str | None, dict, dict]:
        """Get openAccessPdf URL and external IDs.

        Args:
            doi: DOI to look up

        Returns:
            (pdf_url, metadata, external_ids)
            external_ids may contain "ArXiv", "PubMedCentral", etc.
        """
        url = f"{self.BASE_URL}/paper/DOI:{doi}"
        params = {
            "fields": "title,year,authors,openAccessPdf,externalIds",
        }

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        data = await self.get(url, params=params, headers=headers)

        if not data or "error" in data:
            return None, {}, {}

        # Extract open access PDF URL
        oa_pdf = data.get("openAccessPdf") or {}
        pdf_url = oa_pdf.get("url")

        # Extract metadata
        metadata = {
            "title": data.get("title"),
            "year": data.get("year"),
        }

        # Extract external IDs for fallback sources
        external_ids = data.get("externalIds") or {}

        return pdf_url, metadata, external_ids
