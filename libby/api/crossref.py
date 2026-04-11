"""Crossref API client."""

import urllib.parse
from typing import Optional

from libby.api.base import AsyncAPIClient, RateLimit
from libby.models.metadata import BibTeXMetadata


class CrossrefAPI(AsyncAPIClient):
    """Crossref API client."""

    RATE_LIMIT = RateLimit(1, 1)  # 1 req/sec
    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto: Optional[str] = None):
        super().__init__()
        self.mailto = mailto

    async def fetch_by_doi(self, doi: str) -> Optional[dict]:
        """Fetch work metadata by DOI."""
        url = f"{self.BASE_URL}/works/{urllib.parse.quote(doi)}"
        params = {}
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            return data.get("message")
        return None

    async def search_by_title(self, title: str) -> list[dict]:
        """Search works by title keywords."""
        url = f"{self.BASE_URL}/works"
        params = {
            "query.title": title,
            "rows": 10,
        }
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            items = data.get("message", {}).get("items", [])
            return items[:5]  # Return top 5 results
        return []

    def _parse_to_metadata(self, data: dict) -> BibTeXMetadata:
        """Parse Crossref response to BibTeXMetadata."""
        # Extract authors
        authors = []
        if "author" in data:
            for author in data["author"]:
                family = author.get("family", "")
                given = author.get("given", "")
                if family:
                    authors.append(f"{family}, {given}" if given else family)

        # Extract year
        year = None
        if "published-print" in data or "published-online" in data:
            pub = data.get("published-print") or data.get("published-online")
            if pub and "date-parts" in pub:
                date_parts = pub["date-parts"][0]
                if len(date_parts) >= 1:
                    year = date_parts[0]

        return BibTeXMetadata(
            citekey="",  # Will be formatted later
            entry_type=data.get("type", "article"),
            author=authors,
            title=data.get("title", [""])[0] if isinstance(data.get("title"), list) else "",
            year=year,
            doi=data.get("DOI"),
            journal=data.get("container-title", [""])[0] if isinstance(data.get("container-title"), list) else "",
            volume=data.get("volume"),
            number=data.get("issue"),
            pages=data.get("page"),
            publisher=data.get("publisher"),
            url=data.get("URL"),
        )