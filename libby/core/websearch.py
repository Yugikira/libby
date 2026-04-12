"""WebSearcher orchestrates multi-source parallel search."""

import asyncio
import logging
import os
import re
from typing import Optional

from rich.console import Console

from libby.models.config import LibbyConfig
from libby.models.search_result import SearchResult, SearchResults, SerpapiExtraInfo
from libby.models.search_filter import SearchFilter
from libby.api.crossref import CrossrefAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.scholarly import ScholarlyAPI
from libby.api.serpapi import SerpapiAPI

logger = logging.getLogger(__name__)


class WebSearcher:
    """Orchestrates parallel search across multiple sources.

    Search flow:
    1. Crossref + Semantic Scholar + Scholarly in parallel (asyncio.gather)
    2. Serpapi separately (controlled usage, 5 pages)
    3. Merge results by DOI (keep longer values, fill missing fields)
    4. Return SearchResults with serpapi_extra info
    """

    def __init__(self, config: LibbyConfig):
        self.config = config
        self.console = Console()
        self.crossref = CrossrefAPI(mailto=os.getenv("EMAIL"))
        self.s2 = SemanticScholarAPI(api_key=os.getenv("S2_API_KEY"))
        self.scholarly = ScholarlyAPI()
        self.serpapi = SerpapiAPI() if os.getenv("SERPAPI_API_KEY") else None

    async def search(
        self,
        query: str,
        filter: SearchFilter | None = None,
        limit: int = 50,
        skip_serpapi: bool = False,
    ) -> SearchResults:
        """Execute parallel search across multiple sources.

        Args:
            query: Search keywords
            filter: Unified SearchFilter
            limit: Result count per source
            skip_serpapi: Skip Serpapi search (free sources only)

        Returns:
            SearchResults with merged results and serpapi_extra
        """
        sources_used = []
        all_results: list[SearchResult] = []
        serpapi_extra: list[SerpapiExtraInfo] = []

        # 1. Parallel execution: Crossref + S2 + Scholarly
        parallel_results = await asyncio.gather(
            self.crossref.search(query, rows=limit, filter=filter),
            self.s2.search(query, limit=limit, filter=filter),
            self.scholarly.search(query, limit=limit, filter=filter),
            return_exceptions=True,  # Handle errors gracefully
        )

        # Process Crossref results
        if not isinstance(parallel_results[0], Exception):
            crossref_raw = parallel_results[0]
            for item in crossref_raw:
                result = self._parse_crossref(item)
                all_results.append(result)
            if crossref_raw:
                sources_used.append("crossref")
        else:
            logger.warning(f"Crossref search failed: {parallel_results[0]}")

        # Process Semantic Scholar results
        if not isinstance(parallel_results[1], Exception):
            s2_raw = parallel_results[1]
            for item in s2_raw:
                result = self._parse_s2(item)
                all_results.append(result)
            if s2_raw:
                sources_used.append("semantic_scholar")
        else:
            logger.warning(f"Semantic Scholar search failed: {parallel_results[1]}")

        # Process Scholarly results
        if not isinstance(parallel_results[2], Exception):
            scholarly_raw = parallel_results[2]
            for item in scholarly_raw:
                result = self._parse_scholarly(item)
                all_results.append(result)
            if scholarly_raw:
                sources_used.append("scholarly")
        else:
            logger.warning(f"Scholarly search failed: {parallel_results[2]}")

        # 2. Merge by DOI
        merged_results = self._merge_by_doi(all_results)

        # 3. Serpapi separately (controlled usage)
        if not skip_serpapi and self.serpapi:
            api_key = os.getenv("SERPAPI_API_KEY")
            if api_key:
                try:
                    serpapi_raw, quota_reached = await self.serpapi.search(
                        query, api_key, max_pages=5
                    )

                    if quota_reached:
                        self.console.print(
                            "[yellow]Warning: Serpapi quota reached, "
                            "some results may be incomplete[/yellow]"
                        )

                    if serpapi_raw:
                        sources_used.append("serpapi")

                        for item in serpapi_raw:
                            result = self._parse_serpapi(item)
                            serpapi_extra_info = SerpapiExtraInfo(
                                doi=result.doi or self._extract_doi_from_serpapi(item),
                                link=item.get("link"),
                                pdf_link=self._extract_pdf_link(item),
                                cited_by_count=item.get("cited_by", {}).get("total"),
                            )
                            serpapi_extra.append(serpapi_extra_info)

                            # Merge into main results if DOI matches
                            if result.doi:
                                for existing in merged_results:
                                    if existing.doi == result.doi:
                                        existing.merge_from(result)
                                        break
                                else:
                                    merged_results.append(result)
                            elif result.title:
                                # Try title-based merge
                                for existing in merged_results:
                                    if existing.title and existing.title.lower() == result.title.lower():
                                        existing.merge_from(result)
                                        break
                                else:
                                    merged_results.append(result)

                except Exception as e:
                    logger.warning(f"Serpapi search failed: {e}")

        # 4. Return SearchResults
        return SearchResults(
            query=query,
            results=merged_results,
            serpapi_extra=serpapi_extra,
            total_count=len(merged_results),
            sources_used=sources_used,
        )

    def _parse_crossref(self, item: dict) -> SearchResult:
        """Parse Crossref API result to SearchResult."""
        # Title is a list
        title = None
        if item.get("title"):
            if isinstance(item["title"], list):
                title = item["title"][0] if item["title"] else None
            else:
                title = item["title"]

        # Authors in objects
        authors = []
        for author in item.get("author", []):
            family = author.get("family", "")
            given = author.get("given", "")
            if family:
                authors.append(f"{family}, {given}" if given else family)

        # Year in date-parts
        year = None
        pub = item.get("published-print") or item.get("published-online")
        if pub and "date-parts" in pub:
            date_parts = pub["date-parts"]
            if date_parts and date_parts[0]:
                year = date_parts[0][0]

        # Journal
        journal = None
        if item.get("container-title"):
            if isinstance(item["container-title"], list):
                journal = item["container-title"][0] if item["container-title"] else None
            else:
                journal = item["container-title"]

        return SearchResult(
            doi=item.get("DOI"),
            title=title,
            author=authors,
            year=year,
            journal=journal,
            abstract=item.get("abstract"),
            volume=item.get("volume"),
            number=item.get("issue"),
            pages=item.get("page"),
            publisher=item.get("publisher"),
            url=item.get("URL"),
            sources=["crossref"],
        )

    def _parse_s2(self, item: dict) -> SearchResult:
        """Parse Semantic Scholar API result to SearchResult."""
        # DOI from externalIds
        doi = None
        external_ids = item.get("externalIds") or {}
        doi = external_ids.get("DOI")

        # Authors as list of dicts
        authors = []
        for author in item.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Venue or journal
        venue = item.get("venue")
        journal = venue if venue else item.get("journal")

        return SearchResult(
            doi=doi,
            title=item.get("title"),
            author=authors,
            year=item.get("year"),
            journal=journal,
            abstract=item.get("abstract"),
            sources=["semantic_scholar"],
        )

    def _parse_scholarly(self, item: dict) -> SearchResult:
        """Parse Scholarly API result to SearchResult."""
        bib = item.get("bib") or {}

        # Year is string in scholarly
        year = None
        pub_year = bib.get("pub_year")
        if pub_year:
            try:
                year = int(pub_year)
            except ValueError:
                pass

        # Authors
        authors = []
        if item.get("author"):
            if isinstance(item["author"], list):
                authors = item["author"]
            else:
                authors = [item["author"]]

        return SearchResult(
            title=bib.get("title"),
            author=authors,
            year=year,
            url=item.get("pub_url") or item.get("url_scholarbib"),
            sources=["scholarly"],
        )

    def _parse_serpapi(self, item: dict) -> SearchResult:
        """Parse Serpapi API result to SearchResult."""
        pub_info = item.get("publication_info") or {}

        # DOI from publication_info or link
        doi = pub_info.get("doi") or self._extract_doi_from_serpapi(item)

        return SearchResult(
            doi=doi,
            title=item.get("title"),
            url=item.get("link"),
            sources=["serpapi"],
        )

    def _extract_doi_from_serpapi(self, item: dict) -> Optional[str]:
        """Extract DOI from Serpapi result."""
        # Direct DOI in publication_info
        pub_info = item.get("publication_info") or {}
        if pub_info.get("doi"):
            return pub_info["doi"]

        # DOI in link URL (doi.org format)
        link = item.get("link") or ""
        doi_pattern = r"doi\.org/(10\.\d{4,}/[^\s&]+)"
        match = re.search(doi_pattern, link)
        if match:
            return match.group(1)

        return None

    def _extract_pdf_link(self, item: dict) -> Optional[str]:
        """Extract PDF link from Serpapi result."""
        # Check resources for PDF
        resources = item.get("resources") or []
        for res in resources:
            if res.get("file_format") == "PDF":
                return res.get("link")

        # Check if link ends with .pdf
        link = item.get("link") or ""
        if link.endswith(".pdf"):
            return link

        return None

    def _merge_by_doi(self, results: list[SearchResult]) -> list[SearchResult]:
        """Merge results by DOI using SearchResult.merge_from().

        Strategy:
        - Results with same DOI are merged
        - Longer values are kept (handled by merge_from)
        - Results without DOI are kept separately (title-based)
        """
        doi_map: dict[str, SearchResult] = {}
        no_doi_results: list[SearchResult] = []

        for r in results:
            if r.doi:
                if r.doi in doi_map:
                    doi_map[r.doi].merge_from(r)
                else:
                    doi_map[r.doi] = r
            else:
                # Results without DOI - try title-based merge
                if r.title:
                    # Look for matching title in no_doi_results
                    for existing in no_doi_results:
                        if existing.title and existing.title.lower() == r.title.lower():
                            existing.merge_from(r)
                            break
                    else:
                        no_doi_results.append(r)
                else:
                    # No DOI and no title - just append
                    no_doi_results.append(r)

        # Combine DOI-merged and no-DOI results
        merged = list(doi_map.values()) + no_doi_results
        return merged

    async def close(self):
        """Close API sessions."""
        await self.crossref.close()
        await self.s2.close()
        await self.scholarly.close()
        if self.serpapi:
            await self.serpapi.close()