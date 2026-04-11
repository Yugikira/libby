"""Sci-hub PDF URL extractor with FreeProxies support."""

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

    Supports FreeProxies to bypass basic anti-scraping.
    """

    RATE_LIMIT = RateLimit(1, 2)  # 1 req per 2 seconds to be safe

    def __init__(self, scihub_url: str = "https://sci-hub.ru", use_free_proxy: bool = False):
        super().__init__()
        self.scihub_url = scihub_url
        self.use_free_proxy = use_free_proxy
        self._proxy: str | None = None
        self._dirty_proxies: set = set()

    async def get_pdf_url(self, doi: str) -> tuple[str | None, str | None]:
        """Get PDF URL from Sci-hub.

        1. Try with free proxy if enabled
        2. Fetch Sci-hub page: {scihub_url}/{doi}
        3. Parse HTML for PDF embed URL
        4. Handle CAPTCHA detection

        Returns:
            (pdf_url, error_message) - pdf_url if found, error_message if failed
            error_message includes manual download hint if CAPTCHA detected
        """
        url = f"{self.scihub_url}/{doi}"

        # Try with proxy first if enabled
        if self.use_free_proxy:
            proxy = await self._get_free_proxy()
            if proxy:
                self._proxy = proxy

        try:
            html = await self.get_html(url)

            if not html:
                return None, f"Failed to fetch page. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

            # Check for CAPTCHA
            if self._is_captcha_page(html):
                return None, f"CAPTCHA detected. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

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
            # Could be a different page type or blocked
            return None, f"Page loaded but no PDF URL found. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

        except Exception as e:
            return None, f"Request failed: {str(e)}. {MANUAL_DOWNLOAD_HINT.format(scihub_url=self.scihub_url, doi=doi)}"

    async def get_html(self, url: str) -> str | None:
        """Fetch HTML content from URL, optionally via proxy."""
        import aiohttp

        kwargs = {"allow_redirects": True}
        if self._proxy:
            kwargs["proxy"] = self._proxy

        session = await self._get_session()
        try:
            async with session.get(url, **kwargs, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
        except asyncio.TimeoutError:
            logger.debug("Timeout fetching %s", url)
            return None
        except Exception as e:
            logger.debug("Error fetching %s: %s", url, e)
            return None

    def _is_captcha_page(self, html: str) -> bool:
        """Check if the page is a CAPTCHA challenge."""
        captcha_indicators = [
            "captcha",
            "recaptcha",
            "g-recaptcha",
            "cf-turnstile",  # Cloudflare
            "challenge",
        ]
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in captcha_indicators)

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

    async def _get_free_proxy(self) -> str | None:
        """Get a working free proxy from free-proxy library.

        Returns:
            Proxy URL string or None if no working proxy found
        """
        try:
            from fp.fp import FreeProxy
        except ImportError:
            logger.warning("free-proxy not installed, skipping proxy")
            return None

        fp = FreeProxy(timeout=2, rand=True)
        max_tries = 10

        for _ in range(max_tries):
            try:
                proxy = fp.get()
                if proxy in self._dirty_proxies:
                    continue

                # Test proxy
                if await self._check_proxy(proxy):
                    logger.info("Found working proxy: %s", proxy)
                    return proxy

                self._dirty_proxies.add(proxy)
            except Exception as e:
                logger.debug("Error getting proxy: %s", e)

        logger.warning("No working free proxy found after %d tries", max_tries)
        return None

    async def _check_proxy(self, proxy: str) -> bool:
        """Check if a proxy is working.

        Args:
            proxy: Proxy URL (e.g., "http://1.2.3.4:8080")

        Returns:
            True if proxy works, False otherwise
        """
        import aiohttp

        test_url = "http://httpbin.org/ip"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, proxy=proxy, timeout=5) as resp:
                    if resp.status == 200:
                        return True
        except Exception:
            pass

        return False
