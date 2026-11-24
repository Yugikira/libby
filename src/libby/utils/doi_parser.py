"""DOI parsing and normalization utilities."""

import re

# DOI pattern per ISO 26324: prefix/suffix
# prefix = registrant agency code + "." + registrant code
# Common registrant agencies: 10 (Crossref), m2 (mEDRA), 10a (CNKI)
DOI_PATTERN = r'[\da-z]+\.[\da-z]+/[^\s]+'
DOI_URL_PREFIXES = [
    "https://doi.org/",
    "http://doi.org/",
    "doi.org/",
]
DOI_TEXT_PREFIXES = [
    "DOI:",
    "doi:",
    "DOI ",
    "doi ",
]


def is_doi(text: str) -> bool:
    """Check if a string is a DOI.

    Detects:
    - URL format: https://doi.org/xxx (any valid DOI)
    - Prefix format: DOI:xxx, doi:xxx
    - Direct DOI: matches ISO 26324 pattern

    Note: DOI registrant agencies include 10 (Crossref), m2 (mEDRA),
    10a (CNKI), etc. We accept all valid DOI patterns.
    """
    text = text.strip().lower()

    # Check for doi.org URL prefix - always a DOI
    for prefix in DOI_URL_PREFIXES:
        if text.startswith(prefix.lower()):
            return True

    # Check for text prefix
    for prefix in DOI_TEXT_PREFIXES:
        if text.startswith(prefix.lower()):
            return True

    # Check for direct DOI pattern (e.g., "10.1234/abc" or "m2.123/xyz")
    if re.match(DOI_PATTERN, text, re.IGNORECASE):
        return True

    return False


def normalize_doi(doi: str) -> str:
    """Normalize DOI string by removing common prefixes."""
    doi = doi.strip()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("http://doi.org/")
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
    - Various DOI registrant agencies (10, m2, 10a, etc.)
    """
    pattern = r'([\da-z]+\.[\da-z]+/[^\s]+)'

    # First try direct match
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        result = match.group(1)
        # If match ends with hyphen, it might be a hyphen break - try merging
        if result.endswith('-'):
            merged = re.sub(r'-\n', '-', text)
            merged = re.sub(r'\n', ' ', merged)
            match = re.search(pattern, merged, re.IGNORECASE)
            if match:
                return match.group(1)
        return result

    # Try merging hyphen breaks
    merged = re.sub(r'-\n', '-', text)
    merged = re.sub(r'\n', ' ', merged)
    match = re.search(pattern, merged, re.IGNORECASE)
    if match:
        return match.group(1)

    return None