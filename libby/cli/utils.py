"""CLI utilities."""

import sys
import json
import logging
from pathlib import Path

from libby.models.result import BatchResult
from libby.core.metadata import MetadataNotFoundError, SerpapiSearchNeeded
from libby.utils.doi_parser import is_doi

logger = logging.getLogger(__name__)


def read_stdin_lines() -> list[str]:
    """Read lines from stdin if not a TTY."""
    if sys.stdin.isatty():
        return []
    return [line.strip() for line in sys.stdin if line.strip()]


async def process_batch(
    inputs: list[tuple[str, str | None, str | None]],
    extractor,
    file_handler,
    ai_extract: bool = False,
    copy: bool = False,
    use_serpapi: bool = False,
) -> BatchResult:
    """Process batch of inputs.

    Args:
        inputs: List of (input_str, doi, title) tuples
            - (doi_str, doi, None): DOI input
            - (title_str, None, title): Title input
            - (pdf_path, None, None): PDF without metadata (extract from text)
            - (pdf_path, doi, None): PDF with provided DOI (scanned PDFs)
            - (pdf_path, None, title): PDF with provided title (scanned PDFs)
        extractor: MetadataExtractor instance
        file_handler: FileHandler instance
        ai_extract: Use AI for PDF extraction
        copy: Copy PDF instead of moving
        use_serpapi: Use Serpapi when Crossref/S2 fail (no user confirmation in batch)

    Returns:
        BatchResult with succeeded and failed lists
    """
    results = BatchResult()

    for input_item, provided_doi, provided_title in inputs:
        input_path = Path(input_item)

        try:
            # PDF file input
            if input_path.suffix.lower() == ".pdf" and input_path.exists():
                if provided_doi:
                    # PDF with provided DOI (scanned PDF)
                    metadata = await extractor.extract_from_doi(provided_doi)
                elif provided_title:
                    # PDF with provided title (scanned PDF)
                    metadata = await extractor.extract_from_title(provided_title, use_serpapi=use_serpapi)
                else:
                    # PDF without metadata - extract from text
                    metadata = await extractor.extract_from_pdf(input_path, use_ai=ai_extract)

                # Organize file
                file_handler.organize_pdf(input_path, metadata, copy=copy)

            elif input_path.exists():
                # Non-PDF file that exists - unsupported
                raise MetadataNotFoundError(f"Unsupported file type: {input_path}")

            elif provided_doi or is_doi(input_item):
                # DOI input (not a file)
                doi = provided_doi or input_item
                metadata = await extractor.extract_from_doi(doi)

            else:
                # Title input
                title = provided_title or input_item
                metadata = await extractor.extract_from_title(title, use_serpapi=use_serpapi)

            results.succeeded.append({
                "input": input_item,
                "citekey": metadata.citekey,
                "doi": metadata.doi,
                "metadata": metadata.to_dict(),
            })

        except SerpapiSearchNeeded as e:
            # Crossref and S2 failed, Serpapi needed
            # In batch mode, fail the task instead of prompting user
            results.failed.append({
                "input": input_item,
                "error": e.message,
                "needs_serpapi": True,
            })
            logger.warning(f"Serpapi needed for: {input_item}")

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