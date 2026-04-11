"""Citekey formatting."""

import re
import unicodedata

from libby.models.config import CitekeyConfig
from libby.models.metadata import BibTeXMetadata


# Characters invalid in Windows filenames
INVALID_CHARS = r'[<>:"/\\|?*]'


class CitekeyFormatter:
    """Format citekeys from metadata."""

    def __init__(self, config: CitekeyConfig):
        self.pattern = config.pattern
        self.author_words = config.author_words
        self.title_words = config.title_words
        self.title_chars_per_word = config.title_chars_per_word
        self.case = config.case
        self.ascii_only = config.ascii_only
        self.ignored_words = set(config.ignored_words)

    def format(self, metadata: BibTeXMetadata) -> str:
        """Format citekey from metadata."""
        author = self._format_author(metadata.author)
        title = self._format_title(metadata.title)
        year = str(metadata.year or "nd")

        result = self.pattern.format(author=author, title=title, year=year)

        if self.case == "lowercase":
            result = result.lower()
        elif self.case == "camelcase":
            result = self._to_camelcase(result)

        if self.ascii_only:
            result = self._to_ascii(result)

        # Sanitize invalid characters for filesystem
        result = self._sanitize(result)

        return result

    def _sanitize(self, text: str) -> str:
        """Remove invalid filesystem characters."""
        # Replace invalid chars with underscore
        return re.sub(INVALID_CHARS, '_', text)

    def _format_author(self, author: list[str]) -> str:
        """Extract author surname."""
        if not author:
            return "unknown"

        # Take first author
        first_author = author[0] if isinstance(author, list) else author

        # Handle "Last, First" or "First Last" format
        if "," in first_author:
            return first_author.split(",")[0].strip()
        else:
            return first_author.split()[-1]

    def _format_title(self, title: str) -> str:
        """Extract title keywords."""
        if not title:
            return "no_title"

        words = title.split()
        # Filter ignored words
        words = [w for w in words if w.lower() not in self.ignored_words]
        # Limit word count
        words = words[: self.title_words]
        # Limit chars per word
        if self.title_chars_per_word > 0:
            words = [w[: self.title_chars_per_word] for w in words]

        return "_".join(words) if words else "no_title"

    def _to_ascii(self, text: str) -> str:
        """Convert to ASCII."""
        return unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")

    def _to_camelcase(self, text: str) -> str:
        """Convert to camelCase."""
        parts = text.replace("_", " ").split()
        return "".join(word.capitalize() for word in parts)