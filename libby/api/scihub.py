"""Sci-hub PDF URL extractor."""

import re
from libby.api.base import AsyncAPIClient, RateLimit


class ScihubAPI(AsyncAPIClient):
    """Sci-hub PDF URL extractor.

    WARNING: Sci-hub operates in a legal gray area. Use with caution.
    Domain may change; configure via config.scihub_url.
    """

    RATE_LIMIT = RateLimit(1, 2)  # 1 req per 2 seconds to be safe

    def __init__(self, scihub_url: str = "https://sci-hub.ru"):
        super().__init__()
        self.scihub_url = scihub_url

    async def get_pdf_url(self, doi: str) -> str | None:
        """Get PDF URL from Sci-hub.

        1. Fetch Sci-hub page: {scihub_url}/{doi}
        2. Parse HTML for PDF embed URL
        3. Return direct PDF URL

        Returns:
            PDF URL or None if not found
        """
        url = f"{self.scihub_url}/{doi}"

        try:
            # Fetch HTML (need to handle redirects)
            html = await self.get_html(url)

            if not html:
                return None

            pdf_url = self._parse_pdf_url(html)

            if pdf_url:
                # Handle protocol-relative URLs (e.g., "//sci-hub.ru/...")
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                # Handle /downloads path (Sci-hub internal path)
                elif pdf_url.startswith("/downloads"):
                    pdf_url = self.scihub_url + pdf_url

            return pdf_url

        except Exception:
            return None

    async def get_html(self, url: str) -> str | None:
        """Fetch HTML content from URL."""
        session = await self._get_session()
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status == 200:
                return await resp.text()
            return None

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
