"""BibTeX metadata model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BibTeXMetadata:
    """BibTeX metadata entry."""

    citekey: str
    entry_type: str = "article"
    author: list[str] = field(default_factory=list)
    title: str = ""
    year: Optional[int] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "citekey": self.citekey,
            "entry_type": self.entry_type,
            "author": self.author,
            "title": self.title,
            "year": self.year,
            "doi": self.doi,
            "journal": self.journal,
            "volume": self.volume,
            "number": self.number,
            "pages": self.pages,
            "publisher": self.publisher,
            "url": self.url,
            "abstract": self.abstract,
        }