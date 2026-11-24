"""bioRxiv/medRxiv API client."""

from libby.api.base import AsyncAPIClient, RateLimit


class BiorxivAPI(AsyncAPIClient):
    """bioRxiv/medRxiv API for preprint PDFs."""

    RATE_LIMIT = RateLimit(1, 1)  # 1 req/sec
    BASE_URL = "https://api.biorxiv.org"

    async def get_pdf_url(self, doi: str) -> str | None:
        """Get PDF URL for bioRxiv/medRxiv DOIs.

        Args:
            doi: DOI starting with "10.1101/"

        Returns:
            PDF URL or None if not a bioRxiv DOI
        """
        # Check if this is a bioRxiv/medRxiv DOI
        if not doi.startswith("10.1101/"):
            return None

        # Try both servers
        for server in ("biorxiv", "medrxiv"):
            url = f"{self.BASE_URL}/details/{server}/{doi}"

            try:
                data = await self.get(url)

                collection = data.get("collection")
                if collection and len(collection) > 0:
                    # Get latest version
                    latest = collection[-1]
                    version = latest.get("version", 1)

                    return f"https://www.{server}.org/content/{doi}v{version}.full.pdf"

            except Exception:
                # Try next server
                continue

        return None
