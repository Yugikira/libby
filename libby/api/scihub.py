"""Sci-hub PDF URL extractor."""

import re
import asyncio
import logging
from libby.api.base import AsyncAPIClient, RateLimit

logger = logging.getLogger(__name__)

# Manual download instructions for user
MANUAL_DOWNLOAD_HINT = "Manual download: Open {scihub_url}/{doi} in browser"


class ScihubAPI(AsyncAPIClient):
    """Sci-hub PDF URL extractor.

    WARNING: Sci-hub operates in a legal gray area. Use with caution.
    Domain may change; configure via config.scihub_url.
    """

    RATE_LIMIT = RateLimit(1, 2)  # 1 req per 2 seconds to be safe

    def __init__(self, scihub_url: str = "https://sci-hub.ru"):
        super().__init__()
        self.scihub_url = scihub_url

    async def get_pdf_url(self, doi: str) -> tuple[str | None, str | None]:
        """Get PDF URL from Sci-hub.

        1. Fetch Sci-hub page: {scihub_url}/{doi}
        2. Parse HTML for PDF embed URL
        3. Handle CAPTCHA/block detection

        Returns:
            (pdf_url, error_message) - pdf_url if found, error_message if failed
            error_message always includes manual download hint
        """
        url = f"{self.scihub_url}/{doi}"

        try:
            html = await self.get_html(url)

            if not html:
                return None, f"Failed to fetch page. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

            # Check for CAPTCHA/block
            if self._is_blocked_page(html):
                return None, f"Access blocked (CAPTCHA/firewall). {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

            pdf_url = self._parse_pdf_url(html)

            if pdf_url:
                # Handle protocol-relative URLs
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                # Handle /downloads path
                elif pdf_url.startswith("/downloads"):
                    pdf_url = self.scihub_url + pdf_url

                return pdf_url, None

            # Page loaded but no PDF URL found
            return None, f"Page loaded but no PDF URL found. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

        except asyncio.TimeoutError:
            return None, f"Request timed out. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"
        except Exception as e:
            return None, f"Request failed: {str(e)}. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

    async def get_html(self, url: str) -> str | None:
        """Fetch HTML content from URL."""
        import aiohttp

        session = await self._get_session()
        try:
            async with session.get(url, allow_redirects=True, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
        except asyncio.TimeoutError:
            logger.debug("Timeout fetching %s", url)
            return None
        except Exception as e:
            logger.debug("Error fetching %s: %s", url, e)
            return None

    def _is_blocked_page(self, html: str) -> bool:
        """Check if the page is blocked (CAPTCHA, firewall, etc.)."""
        block_indicators = [
            "captcha",
            "recaptcha",
            "g-recaptcha",
            "cf-turnstile",  # Cloudflare
            "challenge",
            "blocked",
            "access denied",
            "cloudflare",
        ]
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in block_indicators)

    def _parse_pdf_url(self, html: str) -> str | None:
        """Extract PDF URL from Sci-hub HTML.

        Supports multiple HTML patterns:
        - <embed src="..."> (primary)
        - <iframe src="...pdf">
        - pdfUrl variable
        - data-url attribute
        """
        # Pattern 1: embed src (primary - matches reference implementation)
        match = re.search(r'<embed[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 2: iframe src with PDF URL
        match = re.search(r'<iframe[^>]+src=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 3: pdfUrl variable
        match = re.search(r'pdfUrl\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 4: data-url attribute
        match = re.search(r'data-url=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)

        return None