"""URL validation utilities for security."""

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Trusted domains for academic PDF downloads
TRUSTED_DOMAINS = [
    # DOI resolution
    "doi.org",
    # Major publishers and repositories
    "springer.com",
    "link.springer.com",
    "wiley.com",
    "onlinelibrary.wiley.com",
    "sciencedirect.com",
    "elsevier.com",
    "nature.com",
    "scientificamerican.com",
    "arxiv.org",
    "pmc.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "biorxiv.org",
    "medrxiv.org",
    "semanticscholar.org",
    "s2-search.firebaseapp.com",  # S2 PDF hosting
    "core.ac.uk",
    "download.core.ac.uk",
    "unpaywall.org",
    # Institutional repositories (common patterns)
    "ink.library.smu.edu.sg",
    "researchportal.bath.ac.uk",
    "openaccess.uva.nl",
    # Web archive
    "web.archive.org",
    # Sci-hub mirrors (for fallback)
    "sci-hub.ru",
    "sci-hub.se",
    "sci-hub.st",
    "sci-hub.sg",
]

# Maximum allowed PDF file size (50 MB)
MAX_PDF_SIZE = 50 * 1024 * 1024


def is_valid_pdf_url(url: str) -> tuple[bool, str]:
    """Validate PDF URL for security.

    Checks:
    1. URL scheme must be https (or http for legacy sources)
    2. Host must not be an internal/private IP (SSRF protection)
    3. Host should be in trusted domains (warning if not)

    Args:
        url: URL string to validate

    Returns:
        (is_valid, error_message) - is_valid=True if safe to download
    """
    if not url:
        return False, "Empty URL"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    # Check scheme - must be http or https
    if parsed.scheme not in ("http", "https"):
        return False, f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed."

    # Prefer HTTPS but allow HTTP for legacy sources
    if parsed.scheme == "http":
        logger.warning(f"Using HTTP (not HTTPS) for: {url}")

    # Check host
    host = parsed.hostname
    if not host:
        return False, "URL has no hostname"

    # SSRF protection: block internal/private IPs
    try:
        # Try to parse as IP address
        ip = ipaddress.ip_address(host)
        # Block private, loopback, link-local, reserved IPs
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, f"Blocked internal IP address: {host}"
        # Block multicast
        if ip.is_multicast:
            return False, f"Blocked multicast IP address: {host}"
    except ValueError:
        # Not an IP address, it's a domain name - OK
        pass

    # Check against trusted domains (warning only, not blocking)
    is_trusted = False
    for trusted in TRUSTED_DOMAINS:
        if host == trusted or host.endswith(f".{trusted}"):
            is_trusted = True
            break

    if not is_trusted:
        logger.warning(f"URL from non-trusted domain: {host}")

    return True, ""


def sanitize_filename(name: str) -> str:
    """Sanitize filename for safe filesystem usage.

    Removes/replaces invalid characters.
    """
    import re
    # Replace invalid filesystem characters with underscore
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', name)
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized