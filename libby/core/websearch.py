"""WebSearcher orchestrates multi-source parallel search."""

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

from rich.console import Console

from libby.models.config import LibbyConfig
from libby.models.search_result import SearchResult, SearchResults, SerpapiExtraInfo, parse_bibtex
from libby.models.search_filter import SearchFilter
from libby.api.crossref import CrossrefAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.serpapi import SerpapiAPI

logger = logging.getLogger(__name__)


class WebSearcher:
    """Orchestrates parallel search across multiple sources.

    Search flow:
    1. Journal resolution (venue ↔ ISSN via Crossref)
    2. Crossref + Semantic Scholar in parallel (asyncio.gather)
    3. Author filtering (post-filter for Crossref/S2)
    4. Serpapi separately (controlled usage, 5 pages)
    5. Merge results by DOI (keep longer values, fill missing fields)
    6. Return SearchResults with serpapi_extra info
    """

    def __init__(self, config: LibbyConfig):
        self.config = config
        self.console = Console()
        self.crossref = CrossrefAPI(mailto=config.get_email())
        self.s2 = SemanticScholarAPI(api_key=config.get_s2_api_key())
        self.serpapi = SerpapiAPI() if config.get_serpapi_api_key() else None

    async def search(
        self,
        query: str,
        filter: SearchFilter | None = None,
        limit: int = 50,
        skip_serpapi: bool = False,
        sources: list[str] | None = None,
    ) -> SearchResults:
        """Execute parallel search across multiple sources.

        Args:
            query: Search keywords
            filter: Unified SearchFilter
            limit: Result count per source
            skip_serpapi: Skip Serpapi search (free sources only)
            sources: List of specific sources to use (crossref, s2, serpapi)
                     If None, uses all free sources (crossref, s2)

        Returns:
            SearchResults with merged results and serpapi_extra
        """
        # Valid source names
        VALID_SOURCES = {"crossref", "s2", "serpapi"}

        # Determine which sources to use
        if sources:
            # Validate source names
            invalid = set(sources) - VALID_SOURCES
            if invalid:
                logger.warning(f"Invalid sources ignored: {invalid}")
            sources = [s for s in sources if s in VALID_SOURCES]
            use_crossref = "crossref" in sources
            use_s2 = "s2" in sources
            use_serpapi = "serpapi" in sources
        else:
            # Default: all free sources, serpapi needs explicit enable
            use_crossref = True
            use_s2 = True
            use_serpapi = not skip_serpapi and self.serpapi is not None

        sources_used = []
        all_results: list[SearchResult] = []
        serpapi_extra: list[SerpapiExtraInfo] = []

        # Use default filter if none provided
        if filter is None:
            filter = SearchFilter()

        # 1. Journal resolution (venue ↔ ISSN) - only if using Crossref
        if use_crossref and (filter.venue or filter.issn):
            filter = await self._resolve_journal_filter(filter)

        # 2. Parallel execution: selected free sources
        parallel_tasks = []
        parallel_names = []

        if use_crossref:
            parallel_tasks.append(self.crossref.search(query, rows=limit, filter=filter))
            parallel_names.append("crossref")

        if use_s2:
            parallel_tasks.append(self.s2.search(query, limit=limit, filter=filter))
            parallel_names.append("s2")

        parallel_results = await asyncio.gather(
            *parallel_tasks,
            return_exceptions=True,  # Handle errors gracefully
        )

        # Process parallel results dynamically
        crossref_results: list[SearchResult] = []
        s2_results: list[SearchResult] = []

        for i, (name, result) in enumerate(zip(parallel_names, parallel_results)):
            if isinstance(result, Exception):
                logger.warning(f"{name} search failed: {result}")
                continue

            if not result:
                continue

            sources_used.append(name)

            if name == "crossref":
                for item in result:
                    crossref_results.append(self._parse_crossref(item))
            elif name == "s2":
                for item in result:
                    s2_results.append(self._parse_s2(item))

        # 3. Author filtering (post-filter for Crossref and S2)
        if filter.author:
            crossref_results = self._filter_by_author(crossref_results, filter.author)
            s2_results = self._filter_by_author(s2_results, filter.author)

        # Combine all results
        all_results = crossref_results + s2_results

        # 4. Merge by DOI
        merged_results = self._merge_by_doi(all_results)

        # 5. Serpapi separately (controlled usage)
        if use_serpapi and self.serpapi:
            api_key = self.config.get_serpapi_api_key()
            if api_key:
                try:
                    serpapi_raw, quota_reached = await self.serpapi.search(
                        query, api_key, max_pages=5, filter=filter
                    )

                    if quota_reached:
                        self.console.print(
                            "[yellow]Warning: Serpapi quota reached, "
                            "some results may be incomplete[/yellow]"
                        )

                    if serpapi_raw:
                        sources_used.append("serpapi")

                        # Fetch BibTeX for all results in parallel
                        bibtex_results = await self._fetch_serpapi_bibtex(serpapi_raw, api_key)

                        for i, item in enumerate(serpapi_raw):
                            result = self._parse_serpapi(item)

                            # Merge BibTeX data if available
                            if i < len(bibtex_results) and bibtex_results[i]:
                                bibtex_data = bibtex_results[i]
                                if bibtex_data:
                                    # Create SearchResult from BibTeX and merge
                                    bibtex_result = SearchResult(
                                        title=bibtex_data.get("title"),
                                        author=bibtex_data.get("author", []),
                                        year=bibtex_data.get("year"),
                                        journal=bibtex_data.get("journal"),
                                        volume=bibtex_data.get("volume"),
                                        number=bibtex_data.get("number"),
                                        pages=bibtex_data.get("pages"),
                                        publisher=bibtex_data.get("publisher"),
                                        abstract=bibtex_data.get("abstract"),
                                        entry_type=bibtex_data.get("entry_type", "article"),
                                    )
                                    result.merge_from(bibtex_result)

                            serpapi_extra_info = SerpapiExtraInfo(
                                doi=result.doi or self._extract_doi_from_serpapi(item),
                                link=item.get("link"),
                                pdf_link=self._extract_pdf_link(item),
                                cited_by_count=item.get("cited_by", {}).get("total"),
                                bibtex_link=self._extract_bibtex_link(item),
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

        # 6. Return SearchResults
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

        # Authors as list of strings
        authors = []
        for author in item.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Journal is a nested object: {name, volume, pages, ...}
        journal_data = item.get("journal") or {}
        journal_name = journal_data.get("name") if journal_data else None
        # Fallback to venue if journal.name is empty
        if not journal_name:
            venue = item.get("venue")
            if venue:  # venue can be empty string ""
                journal_name = venue

        # Extract volume, pages from journal object
        volume = journal_data.get("volume") if journal_data else None
        pages = journal_data.get("pages") if journal_data else None

        return SearchResult(
            doi=doi,
            title=item.get("title"),
            author=authors,
            year=item.get("year"),
            journal=journal_name,
            volume=volume,
            pages=pages,
            abstract=item.get("abstract"),
            sources=["s2"],
        )

    def _parse_serpapi(self, item: dict) -> SearchResult:
        """Parse Serpapi result - extract basic fields as fallback.

        Full metadata (journal, volume, etc.) will be fetched from BibTeX.
        If BibTeX fails, these basic fields serve as fallback:
        - title: item["title"]
        - abstract: item["snippet"]
        - authors: publication_info["authors"][*]["name"]
        - year: from publication_info summary
        - doi: from link or publication_info
        - url: item["link"]
        """
        pub_info = item.get("publication_info") or {}

        # DOI from publication_info or link
        doi = pub_info.get("doi") or self._extract_doi_from_serpapi(item)

        # Authors from publication_info (fallback if BibTeX fails)
        authors = []
        author_list = pub_info.get("authors") or []
        for author_dict in author_list:
            name = author_dict.get("name")
            if name:
                authors.append(name)

        # Year from publication_info summary (fallback if BibTeX fails)
        year = None
        summary = pub_info.get("summary") or ""
        year_match = re.search(r"(\d{4})", summary)
        if year_match:
            try:
                year = int(year_match.group(1))
            except ValueError:
                pass

        # Snippet as abstract
        abstract = item.get("snippet")

        return SearchResult(
            doi=doi,
            title=item.get("title"),
            author=authors,
            year=year,
            abstract=abstract,
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

    def _extract_bibtex_link(self, item: dict) -> Optional[str]:
        """Extract BibTeX link from Serpapi result.

        From inline_links["serpapi_cite_link"] - returns a link that
        when fetched gives a dict with "links" list containing BibTeX link.

        Returns:
            URL to fetch BibTeX citation (requires API key)
        """
        inline_links = item.get("inline_links") or {}
        serpapi_cite_link = inline_links.get("serpapi_cite_link")
        return serpapi_cite_link

    async def _fetch_serpapi_bibtex(self, serpapi_items: list[dict], api_key: str) -> list[Optional[dict]]:
        """Fetch and parse BibTeX for all Serpapi results with limited parallelism.

        Uses Semaphore to limit concurrent workers (configured in serpapi.max_bibtex_workers).

        Args:
            serpapi_items: List of Serpapi search result items
            api_key: Serpapi API key

        Returns:
            List of parsed BibTeX dicts (same order as input, None for failures)
        """
        # Get max workers from config, enforce upper limit
        max_workers = min(
            self.config.serpapi.max_bibtex_workers,
            self.config.serpapi.max_workers_limit
        )

        # Semaphore to limit concurrent Selenium calls
        semaphore = asyncio.Semaphore(max_workers)

        async def fetch_single_bibtex(item: dict) -> Optional[dict]:
            """Fetch BibTeX for single item with semaphore."""
            async with semaphore:
                # Get cite link from inline_links (already in search results)
                inline_links = item.get("inline_links") or {}
                serpapi_cite_link = inline_links.get("serpapi_cite_link")

                if not serpapi_cite_link:
                    return None

                try:
                    # Use SerpapiAPI to get BibTeX
                    bibtex_str = await self.serpapi.get_bibtex(serpapi_cite_link, api_key)
                    if bibtex_str:
                        return parse_bibtex(bibtex_str)
                except Exception as e:
                    logger.debug(f"Failed to fetch BibTeX: {e}")
                return None

        # Fetch all with limited parallelism
        tasks = [fetch_single_bibtex(item) for item in serpapi_items]
        return await asyncio.gather(*tasks)

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

    async def _resolve_journal_filter(self, filter: SearchFilter) -> SearchFilter:
        """Resolve venue ↔ ISSN via Crossref.

        Cases:
        - venue + issn: Verify they match
        - venue only: Query Crossref for ISSN (pick highest similarity)
        - issn only: Query Crossref for journal name

        Args:
            filter: SearchFilter with venue and/or issn

        Returns:
            SearchFilter with _resolved_venue and _resolved_issn set
        """
        # Case 1: Both venue and issn provided - verify match
        if filter.venue and filter.issn:
            journal = await self.crossref.get_journal_by_issn(filter.issn)
            if journal:
                journal_title = journal.get("title", "")
                similarity = self._calculate_similarity(filter.venue, journal_title)

                if similarity < 0.7:  # Threshold for match
                    self.console.print(
                        f"[yellow]Warning: venue '{filter.venue}' may not match "
                        f"ISSN '{filter.issn}' (journal: '{journal_title}')[/yellow]"
                    )
                else:
                    filter._resolved_venue = journal_title
                    filter._resolved_issn = filter.issn
                    filter._resolution_verified = True
            else:
                self.console.print(
                    f"[yellow]Warning: ISSN '{filter.issn}' not found in Crossref[/yellow]"
                )
            return filter

        # Case 2: Only venue provided - query for ISSN
        if filter.venue and not filter.issn:
            journals = await self.crossref.search_journal_by_name(filter.venue)
            if journals:
                # Pick highest similarity match
                best_match = max(
                    journals,
                    key=lambda j: self._calculate_similarity(
                        filter.venue, j.get("title", "")
                    )
                )
                best_title = best_match.get("title", "")
                issns = best_match.get("ISSN", [])
                # Prefer print ISSN (has hyphen)
                issn = next((i for i in issns if "-" in i), issns[0] if issns else None)

                if issn:
                    filter._resolved_venue = best_title
                    filter._resolved_issn = issn
                    self.console.print(
                        f"[green]Resolved: venue '{filter.venue}' → ISSN '{issn}'[/green]"
                    )
                else:
                    self.console.print(
                        f"[yellow]Warning: No ISSN found for venue '{filter.venue}'[/yellow]"
                    )
            else:
                self.console.print(
                    f"[yellow]Warning: Venue '{filter.venue}' not found in Crossref[/yellow]"
                )
            return filter

        # Case 3: Only ISSN provided - query for journal name
        if filter.issn and not filter.venue:
            journal = await self.crossref.get_journal_by_issn(filter.issn)
            if journal:
                journal_title = journal.get("title", "")
                filter._resolved_venue = journal_title
                filter._resolved_issn = filter.issn
                self.console.print(
                    f"[green]Resolved: ISSN '{filter.issn}' → venue '{journal_title}'[/green]"
                )
            else:
                self.console.print(
                    f"[yellow]Warning: ISSN '{filter.issn}' not found in Crossref[/yellow]"
                )
            return filter

        return filter

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using SequenceMatcher.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        # Normalize strings for comparison
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()
        return SequenceMatcher(None, s1, s2).ratio()

    def _filter_by_author(self, results: list[SearchResult], author: str) -> list[SearchResult]:
        """Filter results by author name (fuzzy match).

        Matching rules:
        - Case insensitive
        - Match surname (e.g., "Smith" matches "Smith, John" or "John Smith")
        - Match full name if provided
        - Partial match if author name appears in result author

        Args:
            results: List of SearchResult
            author: Author name to filter

        Returns:
            Filtered list of SearchResult
        """
        if not author:
            return results

        author_lower = author.lower().strip()
        filtered = []

        for result in results:
            for result_author in result.author:
                result_author_lower = result_author.lower()

                # Case 1: Exact match
                if author_lower == result_author_lower:
                    filtered.append(result)
                    break

                # Case 2: Surname match ("Smith, John" format)
                if "," in result_author:
                    surname = result_author.split(",")[0].strip().lower()
                    if author_lower == surname:
                        filtered.append(result)
                        break

                # Case 3: Surname match ("John Smith" format)
                parts = result_author.split()
                if parts:
                    surname = parts[-1].lower()  # Last word is surname
                    if author_lower == surname:
                        filtered.append(result)
                        break

                # Case 4: Partial match (user input appears in author name)
                if author_lower in result_author_lower:
                    filtered.append(result)
                    break

        return filtered

    async def close(self):
        """Close API sessions."""
        await self.crossref.close()
        await self.s2.close()
        if self.serpapi:
            await self.serpapi.close()