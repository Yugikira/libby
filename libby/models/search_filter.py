"""Unified search filter model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchFilter:
    """Unified search filter, each API client converts to native params.

    Provides:
    - Time range filtering (year_from, year_to)
    - Venue filtering (venue name, ISSN)
    - Native params passthrough for advanced users

    Each API client implements conversion:
    - Crossref: filter=from-pub-date:{year},issn:{issn}
    - Semantic Scholar: year={year}, venue={name}
    - Scholarly: Modify query with "after:{year}", "source:{venue}"
    """

    # Time range
    year_from: Optional[int] = None  # Default: current year - 2
    year_to: Optional[int] = None

    # Venue
    venue: Optional[str] = None  # Journal/conference name
    issn: Optional[str] = None   # ISSN for precise matching

    # Native params (passthrough for advanced users)
    native_params: dict = field(default_factory=dict)

    def __post_init__(self):
        """Set default year_from to 2 years ago."""
        if self.year_from is None:
            from datetime import datetime
            self.year_from = datetime.now().year - 2