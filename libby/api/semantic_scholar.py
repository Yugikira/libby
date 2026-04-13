"""Semantic Scholar API client."""

from datetime import datetime

from libby.api.base import AsyncAPIClient, RateLimit
from libby.models.search_filter import SearchFilter


class SemanticScholarAPI(AsyncAPIClient):
    """Semantic Scholar API for paper metadata and OA PDFs.

    Rate limits (per Semantic Scholar docs):
        - With API key: 1 request / second 
        - Without key: 100 requests / 5 minutes 
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None):
        # Rate limit based on API key presence
        if api_key:
            rate_limit = RateLimit(1, 1)  # Conservative: 1 req/sec (docs: 5000 req/5 min)
        else:
            rate_limit = RateLimit(1, 3)  # Conservative: 1 req/3 sec (docs: 100 req/5 min)
        self.RATE_LIMIT = rate_limit

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

    async def search(
        self,
        query: str,
        limit: int = 50,
        filter: SearchFilter | None = None,
    ) -> list[dict]:
        """Search papers, convert SearchFilter to S2 native params.

        Semantic Scholar params:
            year={year} or year={from}-{to}
            venue={venue_name}

        Args:
            query: Search keywords
            limit: Result count
            filter: Unified SearchFilter (default: year_from = current_year - 2)

        Returns:
            Raw result list from S2
        """
        # Create default filter with year_from = current_year - 2
        if filter is None:
            filter = SearchFilter(year_from=datetime.now().year - 2)

        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": query,
            "limit": limit,
            # Note: 'issn' is not a valid S2 field - use externalIds.DOI instead
            "fields": "title,year,authors,abstract,externalIds,venue,journal",
        }

        # Convert SearchFilter to S2 native params
        # S2 API: year=2020 means "papers from 2020 only"
        #         year=2020-2024 means "papers from 2020 to 2024"
        # When year_from is set but year_to is not, use current year as end
        if filter.year_from is not None:
            year_to = filter.year_to
            if year_to is None:
                year_to = datetime.now().year  # Use current year as end
            params["year"] = f"{filter.year_from}-{year_to}"

        if filter.venue:
            params["venue"] = filter.venue

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        data = await self.get(url, params=params, headers=headers)

        # Handle error responses
        if not data or "error" in data:
            return []

        return data.get("data", [])
