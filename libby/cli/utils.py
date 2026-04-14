"""CLI utilities."""

import sys
import json
import logging
import re
from pathlib import Path

from libby.models.result import BatchResult
from libby.core.metadata import MetadataNotFoundError, SerpapiSearchNeeded
from libby.utils.doi_parser import is_doi, normalize_doi

logger = logging.getLogger(__name__)


def read_stdin_lines() -> list[str]:
    """Read lines from stdin if not a TTY."""
    if sys.stdin.isatty():
        return []
    return [line.strip() for line in sys.stdin if line.strip()]


def _normalize_title(title: str) -> str:
    """Normalize title for comparison.

    Args:
        title: Title string

    Returns:
        Normalized title (lowercase, trimmed, single spaces)
    """
    if not title:
        return ""
    # Lowercase, strip, collapse multiple spaces
    normalized = title.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def _verify_doi_match(expected_doi: str, actual_doi: str | None) -> bool:
    """Verify that returned DOI matches expected DOI.

    Args:
        expected_doi: DOI provided by user
        actual_doi: DOI from extracted metadata

    Returns:
        True if DOIs match (normalized), False otherwise
    """
    if not actual_doi:
        return False
    return normalize_doi(expected_doi) == normalize_doi(actual_doi)


def _title_similarity(title1: str, title2: str) -> float:
    """Calculate title similarity based on word overlap (Jaccard).

    Args:
        title1: First title
        title2: Second title

    Returns:
        Similarity score between 0 and 1
    """
    # Normalize strings
    words1 = set(re.findall(r'\w+', _normalize_title(title1)))
    words2 = set(re.findall(r'\w+', _normalize_title(title2)))

    if not words1 or not words2:
        return 0.0

    # Jaccard similarity
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union) if union else 0.0


def _verify_title_match(expected_title: str, actual_title: str | None, threshold: float = 0.80) -> bool:
    """Verify that returned title matches expected title with similarity threshold.

    Args:
        expected_title: Title provided by user
        actual_title: Title from extracted metadata
        threshold: Minimum similarity score (default 0.85)

    Returns:
        True if titles match with similarity >= threshold, False otherwise
    """
    if not actual_title:
        return False
    return _title_similarity(expected_title, actual_title) >= threshold


async def process_batch(
    inputs: list[tuple[str, str | None, str | None]],
    extractor,
    file_handler,
    ai_extract: bool = False,
    copy: bool = False,
    use_serpapi: bool = False,
    output_dir: Path | None = None,
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
        output_dir: Override target directory for PDF files (if specified, use this instead of papers_dir)

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
                    # Verify DOI match
                    if not _verify_doi_match(provided_doi, metadata.doi):
                        raise MetadataNotFoundError(
                            f"DOI mismatch: expected '{provided_doi}', got '{metadata.doi}'"
                        )
                elif provided_title:
                    # PDF with provided title (scanned PDF)
                    metadata = await extractor.extract_from_title(provided_title, use_serpapi=use_serpapi)
                    # Verify title similarity (threshold 0.80)
                    if metadata.title:
                        similarity = _title_similarity(provided_title, metadata.title)
                        if similarity < 0.80:
                            logger.warning(
                                f"Title similarity low: {similarity:.2f} "
                                f"(expected: '{provided_title}', got: '{metadata.title}')"
                            )
                            raise MetadataNotFoundError(
                                f"Title mismatch (similarity {similarity:.2f}): "
                                f"expected '{provided_title}', got '{metadata.title}'"
                            )
                else:
                    # PDF without metadata - extract from text
                    metadata = await extractor.extract_from_pdf(input_path, use_ai=ai_extract)

                # Organize file (use output_dir if specified)
                file_handler.organize_pdf(input_path, metadata, copy=copy, output_dir=output_dir)

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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results.failed, f, indent=2, ensure_ascii=False)