"""DOI parsing and normalization utilities."""

import re


def normalize_doi(doi: str) -> str:
    """Normalize DOI string by removing common prefixes."""
    doi = doi.strip()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("doi.org/")
    doi = doi.removeprefix("DOI:")
    doi = doi.removeprefix("doi:")
    doi = doi.removeprefix("DOI ")
    doi = doi.removeprefix("doi ")
    return doi.lower()


def extract_doi_from_text(text: str) -> str | None:
    """Extract DOI from text, handling line breaks.

    Handles:
    - Hyphen breaks: 10.1234/abc-\ndef -> 10.1234/abc-def
    - Space breaks: 10.1234/abc\n123 -> 10.1234/abc 123
    """
    pattern = r'(10\.\d{4,}/[^\s]+)'

    # First try direct match
    match = re.search(pattern, text)
    if match:
        result = match.group(1)
        # If match ends with hyphen, it might be a hyphen break - try merging
        if result.endswith('-'):
            merged = re.sub(r'-\n', '-', text)
            merged = re.sub(r'\n', ' ', merged)
            match = re.search(pattern, merged)
            if match:
                return match.group(1)
        return result

    # Try merging hyphen breaks
    merged = re.sub(r'-\n', '-', text)
    merged = re.sub(r'\n', ' ', merged)
    match = re.search(pattern, merged)
    if match:
        return match.group(1)

    return None