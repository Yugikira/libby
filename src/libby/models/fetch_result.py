"""Fetch result data model."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FetchResult:
    """Result of PDF fetch operation."""

    doi: str
    success: bool
    source: str | None
    pdf_url: str | None
    pdf_path: Path | None = None
    bib_path: Path | None = None
    metadata: dict | None = field(default_factory=dict)
    error: str | None = None
    source_attempts: list[dict] = field(default_factory=list)  # Detailed cascade log

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "doi": self.doi,
            "success": self.success,
            "source": self.source,
            "pdf_url": self.pdf_url,
            "pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "bib_path": str(self.bib_path) if self.bib_path else None,
            "metadata": self.metadata,
            "error": self.error,
            "source_attempts": self.source_attempts,
        }
