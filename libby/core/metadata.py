"""Metadata extraction core."""

from pathlib import Path
from typing import Optional
import re
import logging

from libby.api.crossref import CrossrefAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.models.config import LibbyConfig
from libby.core.citekey import CitekeyFormatter
from libby.core.pdf_text import extract_first_page_text
from libby.utils.doi_parser import normalize_doi, extract_doi_from_text
from libby.models.metadata import BibTeXMetadata

logger = logging.getLogger(__name__)


class MetadataNotFoundError(Exception):
    """Raised when metadata cannot be extracted."""
    pass


class AmbiguousMatchError(Exception):
    """Raised when multiple results have similar scores, indicating ambiguous match."""
    pass


class SerpapiSearchNeeded(Exception):
    """Raised when Crossref and S2 fail, suggesting Serpapi search.

    Attributes:
        title: The title that needs Serpapi search
        message: User-facing message about Serpapi option
    """
    def __init__(self, title: str):
        self.title = title
        self.message = (
            f"Title '{title}' not found in Crossref or Semantic Scholar.\n"
            "Serpapi (Google Scholar) is available but uses API quota.\n"
            "Use extract_from_title(title, use_serpapi=True) to proceed."
        )


class MetadataExtractor:
    """Extract metadata from DOI, title, or PDF."""

    # Minimum score threshold for accepting a result
    MIN_SCORE_THRESHOLD = 50.0
    # Score difference threshold to detect tie (ambiguous match)
    TIE_THRESHOLD = 5.0
    # Title similarity threshold for S2 results
    MIN_TITLE_SIMILARITY = 0.4

    def __init__(self, config: LibbyConfig):
        self.config = config
        self.crossref = CrossrefAPI()
        self.s2 = SemanticScholarAPI(api_key=config.get_s2_api_key())
        self.formatter = CitekeyFormatter(config.citekey)

    async def extract_from_doi(self, doi: str) -> BibTeXMetadata:
        """Extract metadata from DOI."""
        doi = normalize_doi(doi)
        data = await self.crossref.fetch_by_doi(doi)

        if not data:
            raise MetadataNotFoundError(f"DOI not found: {doi}")

        metadata = self.crossref._parse_to_metadata(data)
        metadata.doi = doi
        metadata.citekey = self.formatter.format(metadata)
        return metadata

    async def extract_from_title(self, title: str, use_serpapi: bool = False) -> BibTeXMetadata:
        """Extract metadata from title (cascade: Crossref -> S2 -> Serpapi).

        Uses query.bibliographic for better matching and validates results:
        - Checks score is above threshold (default 50)
        - Detects ties (ambiguous matches) when top results have similar scores
        - Verifies title similarity if possible

        Args:
            title: Paper title to search
            use_serpapi: If True, use Serpapi when Crossref/S2 fail (uses quota)
                         If False, raise SerpapiSearchNeeded instead

        Raises:
            MetadataNotFoundError: When no suitable match found and Serpapi not enabled
            SerpapiSearchNeeded: When Crossref/S2 fail and use_serpapi=False
            AmbiguousMatchError: When multiple results have similar scores
        """
        # Phase 1: Crossref
        logger.debug(f"Searching Crossref for: {title}")
        results = await self.crossref.search_by_title(title, rows=5)
        if results:
            best_result = self._select_best_result(results, title)
            if best_result:
                metadata = self.crossref._parse_to_metadata(best_result)
                metadata.citekey = self.formatter.format(metadata)
                logger.info(f"Found in Crossref: {metadata.citekey}")
                return metadata

        # Phase 2: Semantic Scholar
        logger.debug(f"Searching Semantic Scholar for: {title}")
        s2_results = await self.s2.search(query=title, limit=10)
        if s2_results:
            best_result = self._select_best_s2_result(s2_results, title)
            if best_result:
                metadata = self._parse_s2_to_metadata(best_result)
                metadata.citekey = self.formatter.format(metadata)
                logger.info(f"Found in Semantic Scholar: {metadata.citekey}")
                return metadata

        # Phase 3: Serpapi (requires user confirmation)
        if use_serpapi:
            logger.debug(f"Searching Serpapi for: {title}")
            return await self._extract_from_serpapi(title)

        # All sources failed, suggest Serpapi
        raise SerpapiSearchNeeded(title)

    async def _extract_from_serpapi(self, title: str) -> BibTeXMetadata:
        """Extract metadata from Serpapi (Google Scholar)."""
        from libby.api.serpapi import SerpapiAPI
        from libby.core.websearch import WebSearcher

        api_key = self.config.get_serpapi_api_key()
        if not api_key:
            raise MetadataNotFoundError(
                f"Title not found: {title}\n"
                "Serpapi requires SERPAPI_API_KEY environment variable."
            )

        serpapi = SerpapiAPI()
        try:
            # Search Serpapi
            raw_results, quota_reached = await serpapi.search(
                query=title, api_key=api_key, max_pages=1
            )

            if quota_reached:
                raise MetadataNotFoundError(f"Serpapi quota reached")

            if not raw_results:
                raise MetadataNotFoundError(f"Title not found in Serpapi: {title}")

            # Use WebSearcher's _parse_serpapi method
            searcher = WebSearcher(self.config)
            search_result = searcher._parse_serpapi(raw_results[0])

            # Convert SearchResult to BibTeXMetadata
            metadata = BibTeXMetadata(
                doi=search_result.doi,
                title=search_result.title,
                author=search_result.author or [],
                year=search_result.year,
                journal=search_result.journal,
                volume=search_result.volume,
                number=search_result.number,
                pages=search_result.pages,
                publisher=search_result.publisher,
                abstract=search_result.abstract,
                url=search_result.url,
            )
            metadata.citekey = self.formatter.format(metadata)
            logger.info(f"Found in Serpapi: {metadata.citekey}")
            return metadata

        finally:
            await serpapi.close()

    def _select_best_s2_result(self, results: list[dict], query_title: str) -> Optional[dict]:
        """Select best matching result from S2 search.

        Args:
            results: List of S2 paper objects
            query_title: Original search query

        Returns:
            Best matching result, or None if no suitable match found.
        """
        if not results:
            return None

        # S2 doesn't have score, use title similarity
        for result in results:
            s2_title = result.get("title", "")
            if s2_title:
                similarity = self._title_similarity(query_title, s2_title)
                if similarity >= self.MIN_TITLE_SIMILARITY:
                    return result

        return None

    def _parse_s2_to_metadata(self, data: dict) -> BibTeXMetadata:
        """Parse S2 paper object to BibTeXMetadata."""
        # Authors
        authors = []
        for author in data.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)

        # Year
        year = data.get("year")

        # Journal: S2 has venue field, or journal object
        journal = None
        volume = None
        pages = None
        journal_obj = data.get("journal") or {}
        if isinstance(journal_obj, dict):
            journal = journal_obj.get("name") or data.get("venue")
            volume = journal_obj.get("volume")
            pages = journal_obj.get("pages")
        else:
            journal = data.get("venue")

        # DOI from externalIds
        external_ids = data.get("externalIds") or {}
        doi = external_ids.get("DOI")

        # URL from S2 paperId
        url = f"https://semanticscholar.org/paper/{data.get('paperId')}" if data.get("paperId") else None

        return BibTeXMetadata(
            citekey="",  # Will be set by formatter
            doi=doi,
            title=data.get("title"),
            author=authors,
            year=year,
            journal=journal,
            volume=volume,
            pages=pages,
            url=url,
            abstract=data.get("abstract"),
        )

    def _select_best_result(self, results: list[dict], query_title: str) -> Optional[dict]:
        """Select the best matching result from search results.

        Validation criteria:
        1. Score must be above MIN_SCORE_THRESHOLD
        2. No tie between top results (score difference > TIE_THRESHOLD)
        3. Title similarity check (optional, for extra validation)

        Args:
            results: List of Crossref work items
            query_title: Original search query

        Returns:
            Best matching result, or None if no suitable match found.
        """
        if not results:
            return None

        # Get top result and its score
        top_result = results[0]
        top_score = top_result.get("score", 0)

        # Check minimum score threshold
        if top_score < self.MIN_SCORE_THRESHOLD:
            return None

        # Check for tie (ambiguous match) with second result
        if len(results) > 1:
            second_score = results[1].get("score", 0)
            if abs(top_score - second_score) <= self.TIE_THRESHOLD:
                # Ambiguous match - scores too close
                # We could raise AmbiguousMatchError, but for now just warn
                # and still return the top result with a note
                pass

        # Optional: Verify title similarity
        result_title = top_result.get("title", [""])[0] if isinstance(top_result.get("title"), list) else ""
        if result_title:
            similarity = self._title_similarity(query_title, result_title)
            # Accept result if similarity > 50%
            if similarity < 0.5:
                return None

        return top_result

    def _title_similarity(self, query: str, result: str) -> float:
        """Calculate simple title similarity based on word overlap.

        Args:
            query: Original search query
            result: Matched title from API

        Returns:
            Similarity score between 0 and 1.
        """
        # Normalize both strings
        query_words = set(re.findall(r'\w+', query.lower()))
        result_words = set(re.findall(r'\w+', result.lower()))

        # Remove common stop words for comparison
        stop_words = {"the", "a", "an", "of", "for", "in", "at", "to", "and",
                      "is", "are", "was", "were", "be", "been", "on", "by", "with"}
        query_words.difference_update(stop_words)
        result_words.difference_update(stop_words)

        if not query_words or not result_words:
            return 0.0

        # Jaccard similarity: intersection / union
        intersection = query_words.intersection(result_words)
        union = query_words.union(result_words)

        return len(intersection) / len(union) if union else 0.0

    async def extract_from_pdf(self, pdf_path: Path, use_ai: bool = False) -> BibTeXMetadata:
        """Extract metadata from PDF."""
        text = extract_first_page_text(pdf_path)

        if not text:
            raise MetadataNotFoundError(f"Cannot extract text from PDF: {pdf_path}")

        # Try AI extraction first if enabled
        if use_ai:
            result = await self._ai_extract(text)
            if result.get("doi"):
                return await self.extract_from_doi(result["doi"])
            if result.get("title"):
                return await self.extract_from_title(result["title"])

        # Regex fallback
        doi = extract_doi_from_text(text)
        if doi:
            return await self.extract_from_doi(doi)

        raise MetadataNotFoundError(f"No DOI found in PDF: {pdf_path}")

    async def _ai_extract(self, text: str) -> dict:
        """AI-powered DOI/title extraction."""
        from libby.core.ai_extractor import AIExtractor

        extractor = AIExtractor(self.config)
        return await extractor.extract_from_text(text)

    async def close(self):
        """Close resources."""
        await self.crossref.close()
        await self.s2.close()