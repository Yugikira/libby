"""Metadata extraction core."""

from pathlib import Path
from typing import Optional

from libby.api.crossref import CrossrefAPI
from libby.models.config import LibbyConfig
from libby.core.citekey import CitekeyFormatter
from libby.core.pdf_text import extract_first_page_text
from libby.utils.doi_parser import normalize_doi, extract_doi_from_text
from libby.models.metadata import BibTeXMetadata


class MetadataNotFoundError(Exception):
    """Raised when metadata cannot be extracted."""
    pass


class MetadataExtractor:
    """Extract metadata from DOI, title, or PDF."""

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
        """Extract metadata from title (cascade: Crossref -> S2 -> scholarly)."""
        # Phase 1: Crossref
        results = await self.crossref.search_by_title(title)
        if results:
            metadata = self.crossref._parse_to_metadata(results[0])
            metadata.citekey = self.formatter.format(metadata)
            return metadata

        # Phase 2: Semantic Scholar (TODO)
        # Phase 3: scholarly (TODO)

        raise MetadataNotFoundError(f"Title not found: {title}")

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