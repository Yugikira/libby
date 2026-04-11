"""CLI utilities."""

import sys
import json
from pathlib import Path

from libby.models.result import BatchResult
from libby.core.metadata import MetadataNotFoundError
from libby.utils.doi_parser import is_doi


def read_stdin_lines() -> list[str]:
    """Read lines from stdin if not a TTY."""
    if sys.stdin.isatty():
        return []
    return [line.strip() for line in sys.stdin if line.strip()]


async def process_batch(
    inputs: list[str],
    extractor,
    file_handler,
    ai_extract: bool = False,
    copy: bool = False,
) -> BatchResult:
    """Process batch of inputs."""
    results = BatchResult()

    for input_item in inputs:
        input_path = Path(input_item)

        try:
            if input_path.suffix.lower() == ".pdf":
                metadata = await extractor.extract_from_pdf(input_path, use_ai=ai_extract)
            elif input_path.exists():
                raise MetadataNotFoundError(f"Unsupported file type: {input_path}")
            elif is_doi(input_item):
                metadata = await extractor.extract_from_doi(input_item)
            else:
                metadata = await extractor.extract_from_title(input_item)

            # Organize file if PDF
            if input_path.suffix.lower() == ".pdf" and input_path.exists():
                file_handler.organize_pdf(input_path, metadata, copy=copy)

            results.succeeded.append({
                "input": input_item,
                "citekey": metadata.citekey,
                "doi": metadata.doi,
                "metadata": metadata.to_dict(),
            })

        except Exception as e:
            results.failed.append({
                "input": input_item,
                "error": str(e),
            })

    return results


def save_failed_tasks(results: BatchResult, path: Path):
    """Save failed tasks to JSON file."""
    with open(path, "w") as f:
        json.dump(results.failed, f, indent=2)