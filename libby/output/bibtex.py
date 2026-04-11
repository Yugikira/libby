"""BibTeX format output."""

from libby.models.metadata import BibTeXMetadata


class BibTeXFormatter:
    """Format metadata as BibTeX."""

    def format(self, metadata: BibTeXMetadata) -> str:
        """Format single entry as BibTeX."""
        lines = [
            f"@{metadata.entry_type}{{{metadata.citekey},",
            f"  author = {{{self._format_authors(metadata.author)}}},",
            f"  title = {{{metadata.title}}},",
        ]

        if metadata.year:
            lines.append(f"  year = {{{metadata.year}}},")
        if metadata.doi:
            lines.append(f"  doi = {{{metadata.doi}}},")
        if metadata.journal:
            lines.append(f"  journal = {{{metadata.journal}}},")
        if metadata.volume:
            lines.append(f"  volume = {{{metadata.volume}}},")
        if metadata.number:
            lines.append(f"  number = {{{metadata.number}}},")
        if metadata.pages:
            lines.append(f"  pages = {{{metadata.pages}}},")
        if metadata.publisher:
            lines.append(f"  publisher = {{{metadata.publisher}}},")
        if metadata.url:
            lines.append(f"  url = {{{metadata.url}}},")

        lines.append("}")
        return "\n".join(lines)

    def format_batch(self, metadata_list: list[BibTeXMetadata]) -> str:
        """Format multiple entries as BibTeX."""
        return "\n\n".join(self.format(m) for m in metadata_list)

    def _format_authors(self, authors: list[str]) -> str:
        """Format authors for BibTeX."""
        return " and ".join(authors)