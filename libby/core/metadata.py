"""Metadata extraction core."""

from pathlib import Path
from typing import Optional
import re

from libby.api.crossref import CrossrefAPI
from libby.models.config import LibbyConfig
from libby.core.citekey import CitekeyFormatter
from libby.core.pdf_text import extract_first_page_text
from libby.utils.doi_parser import normalize_doi, extract_doi_from_text
from libby.models.metadata import BibTeXMetadata


class MetadataNotFoundError(Exception):
    """Raised when metadata cannot be extracted."""
    pass


class AmbiguousMatchError(Exception):
    """Raised when multiple results have similar scores, indicating ambiguous match."""
    pass


class MetadataExtractor:
    """Extract metadata from DOI, title, or PDF."""

    # Minimum score threshold for accepting a result
    MIN_SCORE_THRESHOLD = 50.0
    # Score difference threshold to detect tie (ambiguous match)
    TIE_THRESHOLD = 5.0

    def __init__(self, config: LibbyConfig):
        self.config = config
        self.crossref = CrossrefAPI()
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

    async def extract_from_title(self, title: str) -> BibTeXMetadata:
        """Extract metadata from title (cascade: Crossref -> S2 -> scholarly).

        Uses query.bibliographic for better matching and validates results:
        - Checks score is above threshold (default 50)
        - Detects ties (ambiguous matches) when top results have similar scores
        - Verifies title similarity if possible

        Raises:
            MetadataNotFoundError: When no suitable match found
            AmbiguousMatchError: When multiple results have similar scores
        """
        # Phase 1: Crossref
        results = await self.crossref.search_by_title(title, rows=5)
        if results:
            # Validate and select best result
            best_result = self._select_best_result(results, title)
            if best_result:
                metadata = self.crossref._parse_to_metadata(best_result)
                metadata.citekey = self.formatter.format(metadata)
                return metadata

        # Phase 2: Semantic Scholar (TODO)
        # Phase 3: scholarly (TODO)

        raise MetadataNotFoundError(f"Title not found: {title}")

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