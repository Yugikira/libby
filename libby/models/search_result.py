"""Search result models with multi-source field merging."""

from dataclasses import dataclass, field
from typing import Optional
import json
import re


def parse_bibtex(bibtex_str: str) -> dict:
    """Parse BibTeX string to dict.

    Args:
        bibtex_str: BibTeX entry string

    Returns:
        Dict with parsed fields: entry_type, citekey, title, author, journal,
        year, volume, number, pages, publisher, url, abstract
    """
    if not bibtex_str:
        return {}

    # Extract entry type and citekey
    type_match = re.match(r'@(\w+)\{([^,]+),', bibtex_str.strip())
    if not type_match:
        return {}

    entry_type = type_match.group(1)
    citekey = type_match.group(2)

    # Extract fields using regex
    fields = {}

    # Match field = {value} or field = "value" or field = number
    field_pattern = r'(\w+)\s*=\s*(?:\{([^}]*)\}|"([^"]*)"|(\d+))'
    for match in re.finditer(field_pattern, bibtex_str, re.IGNORECASE):
        field_name = match.group(1).lower()
        # Value is in group 2 (curly braces), 3 (quotes), or 4 (number)
        value = match.group(2) or match.group(3) or match.group(4)
        if value:
            fields[field_name] = value.strip()

    # Parse authors (separated by " and ")
    authors = []
    if "author" in fields:
        author_str = fields["author"]
        # Split by " and " or " and\n"
        author_parts = re.split(r'\s+and\s+', author_str, flags=re.IGNORECASE)
        authors = [a.strip().strip(',') for a in author_parts if a.strip()]

    return {
        "entry_type": entry_type,
        "citekey": citekey,
        "title": fields.get("title"),
        "author": authors,
        "journal": fields.get("journal"),
        "year": int(fields["year"]) if fields.get("year") and fields["year"].isdigit() else None,
        "volume": fields.get("volume"),
        "number": fields.get("number"),
        "pages": fields.get("pages"),
        "publisher": fields.get("publisher"),
        "url": fields.get("url"),
        "abstract": fields.get("abstract"),
    }


@dataclass
class SearchResult:
    """Single search result, supports field merging from multiple sources."""

    doi: Optional[str] = None
    title: Optional[str] = None
    author: list[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    abstract: Optional[str] = None

    # Source tracking
    sources: list[str] = field(default_factory=list)

    # BibTeX fields
    entry_type: str = "article"
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None

    def merge_from(self, other: "SearchResult") -> "SearchResult":
        """Merge another result, fill missing fields.

        Strategy:
        - If self field is empty, fill from other
        - Keep longer value if both have same field
        - Combine sources list
        """
        if not self.doi and other.doi:
            self.doi = other.doi

        # Title: keep longer
        if not self.title and other.title:
            self.title = other.title
        elif self.title and other.title and len(other.title) > len(self.title):
            self.title = other.title

        # Author: fill if empty
        if not self.author and other.author:
            self.author = other.author

        # Year: fill if empty
        if not self.year and other.year:
            self.year = other.year

        # Journal: keep longer
        if not self.journal and other.journal:
            self.journal = other.journal
        elif self.journal and other.journal and len(other.journal) > len(self.journal):
            self.journal = other.journal

        # Abstract: keep longer
        if not self.abstract and other.abstract:
            self.abstract = other.abstract
        elif self.abstract and other.abstract and len(other.abstract) > len(self.abstract):
            self.abstract = other.abstract

        # Combine sources (avoid duplicates)
        for src in other.sources:
            if src not in self.sources:
                self.sources.append(src)

        # BibTeX fields: fill if empty
        if not self.volume and other.volume:
            self.volume = other.volume
        if not self.number and other.number:
            self.number = other.number
        if not self.pages and other.pages:
            self.pages = other.pages
        if not self.publisher and other.publisher:
            self.publisher = other.publisher
        if not self.url and other.url:
            self.url = other.url

        return self

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "doi": self.doi,
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "journal": self.journal,
            "abstract": self.abstract,
            "sources": self.sources,
            "entry_type": self.entry_type,
            "volume": self.volume,
            "number": self.number,
            "pages": self.pages,
            "publisher": self.publisher,
            "url": self.url,
        }


@dataclass
class SerpapiExtraInfo:
    """Serpapi extra info, stored separately.

    Contains link information for user follow-up actions.
    """

    doi: Optional[str] = None
    link: Optional[str] = None
    pdf_link: Optional[str] = None
    cited_by_count: Optional[int] = None
    related_articles_link: Optional[str] = None
    bibtex_link: Optional[str] = None  # Link to fetch BibTeX citation

    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "link": self.link,
            "pdf_link": self.pdf_link,
            "cited_by_count": self.cited_by_count,
            "related_articles_link": self.related_articles_link,
            "bibtex_link": self.bibtex_link,
        }


@dataclass
class SearchResults:
    """Batch search results."""

    query: str
    results: list[SearchResult]
    serpapi_extra: list[SerpapiExtraInfo] = field(default_factory=list)
    total_count: int = 0
    sources_used: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Output JSON format."""
        data = {
            "query": self.query,
            "total_count": self.total_count,
            "sources_used": self.sources_used,
            "results": [r.to_dict() for r in self.results],
            "serpapi_extra": [e.to_dict() for e in self.serpapi_extra],
        }
        return json.dumps(data, indent=2)

    def to_bibtex(self, citekey_config) -> str:
        """Output BibTeX format using existing citekey logic."""
        from libby.core.citekey import CitekeyFormatter
        from libby.models.metadata import BibTeXMetadata
        from libby.output.bibtex import BibTeXFormatter

        formatter = BibTeXFormatter()
        citekey_gen = CitekeyFormatter(citekey_config)

        bibtex_entries = []
        for r in self.results:
            if r.doi:  # Only output entries with DOI
                metadata = BibTeXMetadata(
                    citekey=citekey_gen.format(r),
                    entry_type=r.entry_type,
                    author=r.author,
                    title=r.title or "",
                    year=r.year,
                    doi=r.doi,
                    journal=r.journal,
                    volume=r.volume,
                    number=r.number,
                    pages=r.pages,
                    publisher=r.publisher,
                    url=r.url,
                )
                bibtex_entries.append(formatter.format(metadata))

        return "\n".join(bibtex_entries)