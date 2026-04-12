"""Crossref API client."""

import urllib.parse
from typing import Optional

from libby.api.base import AsyncAPIClient, RateLimit
from libby.models.metadata import BibTeXMetadata
from libby.models.search_filter import SearchFilter


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

    async def search_by_title(self, title: str, rows: int = 5) -> list[dict]:
        """Search works by bibliographic query.

        Uses query.bibliographic which searches only bibliographic metadata
        (title, author, journal, year, etc.) for better accuracy.

        Args:
            title: Search query (can include title, author, year, etc.)
            rows: Number of results to return (default 5, max 10)

        Returns:
            List of work items sorted by relevance score.
        """
        url = f"{self.BASE_URL}/works"
        params = {
            "query.bibliographic": title,
            "rows": min(rows, 10),
        }
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            items = data.get("message", {}).get("items", [])
            return items
        return []

    async def search(
        self,
        query: str,
        rows: int = 50,
        filter: SearchFilter | None = None,
    ) -> list[dict]:
        """Search papers, convert SearchFilter to Crossref native params.

        Crossref filter syntax:
            from-pub-date:{year}
            until-pub-date:{year}
            issn:{issn}

        Args:
            query: Search keywords
            rows: Result count (default 50)
            filter: Unified SearchFilter

        Returns:
            Raw result list from Crossref
        """
        # Use default filter if none provided
        if filter is None:
            filter = SearchFilter()

        # Build Crossref filter string
        filter_parts = []

        if filter.year_from:
            filter_parts.append(f"from-pub-date:{filter.year_from}")
        if filter.year_to:
            filter_parts.append(f"until-pub-date:{filter.year_to}")
        if filter.issn:
            filter_parts.append(f"issn:{filter.issn}")

        # Add native params
        for key, value in filter.native_params.items():
            filter_parts.append(f"{key}:{value}")

        # Build request params
        url = f"{self.BASE_URL}/works"
        params = {
            "query.bibliographic": query,
            "rows": rows,
        }

        if filter_parts:
            params["filter"] = ",".join(filter_parts)

        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            items = data.get("message", {}).get("items", [])
            return items
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

    async def get_oa_link(self, doi: str) -> tuple[str | None, dict]:
        """Get open access PDF URL from Crossref metadata.

        Returns:
            (pdf_url, metadata) or (None, {}) if not found
        """
        data = await self.fetch_by_doi(doi)
        if not data:
            return None, {}

        # Check for open access / text-mining link
        for link in data.get("link", []):
            content_type = link.get("content-type", "")
            intended = link.get("intended", "")

            if intended == "text-mining" or "pdf" in content_type:
                pdf_url = link.get("URL")
                if pdf_url:
                    meta = {
                        "title": data.get("title", [""])[0] if isinstance(data.get("title"), list) else "",
                        "year": data.get("year"),
                    }
                    return pdf_url, meta

        return None, {}

    async def get_journal_by_issn(self, issn: str) -> Optional[dict]:
        """Get journal metadata by ISSN.

        Args:
            issn: ISSN (e.g., "0028-0836")

        Returns:
            Journal metadata dict with title, ISSN, publisher, etc.
            None if not found.
        """
        url = f"{self.BASE_URL}/journals/{issn}"
        params = {}
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            return data.get("message")
        return None

    async def search_journal_by_name(self, name: str, rows: int = 5) -> list[dict]:
        """Search journals by name.

        Args:
            name: Journal name to search
            rows: Number of results (default 5)

        Returns:
            List of journal metadata dicts, sorted by relevance.
            Each dict contains: title, ISSN, publisher, scores.
        """
        url = f"{self.BASE_URL}/journals"
        params = {
            "query": name,
            "rows": rows,
        }
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            items = data.get("message", {}).get("items", [])
            return items
        return []