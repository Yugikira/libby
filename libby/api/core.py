"""CORE.ac.uk API client for institutional repository access."""

from libby.api.base import AsyncAPIClient, RateLimit


class CoreAPI(AsyncAPIClient):
    """CORE.ac.uk API for institutional repository PDFs.

    CORE aggregates millions of open access papers from repositories
    worldwide. Can find OA versions that Unpaywall doesn't track.
    """

    RATE_LIMIT = RateLimit(10, 1)  # 10 req/sec (free API)
    BASE_URL = "https://api.core.ac.uk/v3"

    async def get_pdf_url(self, doi: str) -> tuple[str | None, dict]:
        """Search for PDF download URL by DOI.

        Args:
            doi: Paper DOI

        Returns:
            (pdf_url, metadata) - pdf_url if found, empty dict if not
        """
        url = f"{self.BASE_URL}/search/works"
        params = {"q": f'doi:"{doi}"'}

        data = await self.get(url, params=params)

        if not data or "results" not in data:
            return None, {}

        # Find result with valid download URL
        for result in data.get("results", []):
            download_url = result.get("downloadUrl")
            if download_url and download_url.endswith(".pdf"):
                metadata = {
                    "title": result.get("title"),
                    "year": result.get("yearPublished"),
                }
                return download_url, metadata

        return None, {}