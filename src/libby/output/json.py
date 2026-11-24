"""JSON format output."""

import json

from libby.models.metadata import BibTeXMetadata


class JSONFormatter:
    """Format metadata as JSON."""

    def format(self, metadata: BibTeXMetadata) -> str:
        """Format single entry as JSON."""
        return json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2)

    def format_batch(self, metadata_list: list[BibTeXMetadata]) -> str:
        """Format multiple entries as JSON."""
        return json.dumps([m.to_dict() for m in metadata_list], ensure_ascii=False, indent=2)