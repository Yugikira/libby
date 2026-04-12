"""Serpapi Google Scholar client."""

import asyncio
import logging
from typing import Optional

from libby.api.base import AsyncAPIClient, RateLimit
from libby.models.search_filter import SearchFilter

logger = logging.getLogger(__name__)


class SerpapiConfirmationNeeded(Exception):
    """Raised when Serpapi confirmation is needed.

    All free sources failed, user must confirm API usage.
    """

    def __init__(self, doi: str):
        self.doi = doi
        self.message = (
            "All free sources failed to find PDF.\n"
            "Serpapi Google Scholar is available but uses API quota.\n"
            "Do you want to try Serpapi? (y/n)"
        )


class SerpapiAPI(AsyncAPIClient):
    """Serpapi Google Scholar API."""

    RATE_LIMIT = RateLimit(1, 5)  # 1 req per 5 seconds
    BASE_URL = "https://serpapi.com/search"

    async def get_bibtex(self, serpapi_cite_link: str, api_key: str) -> Optional[str]:
        """Fetch BibTeX citation using the cite link from search results.

        Uses aiohttp first, falls back to Selenium if blocked (403).

        Args:
            serpapi_cite_link: The serpapi_cite_link from inline_links
            api_key: Serpapi API key

        Returns:
            BibTeX string or None if not found
        """
        if not serpapi_cite_link:
            return None

        # Add API key to the cite link
        full_url = f"{serpapi_cite_link}&api_key={api_key}"

        # Get cite data (contains BibTeX link)
        cite_data = await self.get(full_url, {})

        if not cite_data or "links" not in cite_data:
            return None

        # Find BibTeX link
        bibtex_url = None
        for link_item in cite_data.get("links", []):
            if link_item.get("name") == "BibTeX":
                bibtex_url = link_item.get("link")
                break

        if not bibtex_url:
            return None

        # Try aiohttp first
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(bibtex_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except Exception as e:
            logger.debug(f"aiohttp failed for BibTeX: {e}")

        # Fallback to Selenium (handles 403 from Google)
        return await self._fetch_bibtex_selenium(bibtex_url)

    async def _fetch_bibtex_selenium(self, bibtex_url: str) -> Optional[str]:
        """Fetch BibTeX using Selenium WebDriver (fallback for 403).

        Note: headless mode is detected by Google, must use visible browser.

        Args:
            bibtex_url: Google Scholar BibTeX URL

        Returns:
            BibTeX string or None
        """
        def _sync_fetch():
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, WebDriverException

            chrome_options = Options()
            # NOTE: headless mode is detected by Google Scholar, causes failure
            # chrome_options.add_argument("--headless")  # Don't use headless!
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            try:
                driver = webdriver.Chrome(options=chrome_options)
                driver.get(bibtex_url)

                # Wait for BibTeX text (in <pre> tag)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "pre"))
                )

                # Get BibTeX text
                bibtex_text = driver.find_element(By.TAG_NAME, "pre").text
                driver.quit()
                return bibtex_text

            except (TimeoutException, WebDriverException) as e:
                logger.warning(f"Selenium failed for BibTeX: {e}")
                try:
                    driver.quit()
                except:
                    pass
                return None

        # Run in thread pool (Selenium is sync)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_fetch)

    async def get_pdf_url(self, doi: str, api_key: str) -> str | None:
        """Search Google Scholar for PDF link via Serpapi.

        Args:
            doi: DOI to search
            api_key: Serpapi API key

        Returns:
            PDF URL or None if not found
        """
        params = {
            "engine": "google_scholar",
            "q": doi,
            "api_key": api_key,
        }

        data = await self.get(self.BASE_URL, params=params)

        if not data or "error" in data:
            return None

        # Only check the first organic result (most relevant match)
        organic_results = data.get("organic_results", [])
        if not organic_results:
            return None

        result = organic_results[0]

        # Check main link for PDF
        link = result.get("link", "")
        if link.endswith(".pdf"):
            return link

        # Check for PDF resource
        resources = result.get("resources", [])
        for res in resources:
            if res.get("file_format") == "PDF":
                return res.get("link")

        return None

    async def search(
        self,
        query: str,
        api_key: str,
        max_pages: int = 5,
        filter: SearchFilter | None = None,
    ) -> tuple[list[dict], bool]:
        """Search Google Scholar via Serpapi.

        Controlled API usage:
        - Max 5 pages per search (50 results)
        - Retry on failure (max 2 per page)

        Filter support:
        - author: Added as "author:{name}" in query
        - venue: Added as "source:{venue}" in query
        - year_from/year_to: Use as_ylo/as_yhi parameters

        Args:
            query: Search keywords
            api_key: Serpapi API key
            max_pages: Max pages to fetch
            filter: SearchFilter for author, venue, year filtering

        Returns:
            (results, quota_reached)
            quota_reached=True means skip Serpapi
        """
        all_results: list[dict] = []
        quota_reached = False

        # Build enhanced query with author and venue
        enhanced_query = query
        if filter:
            # Author: embed in query
            if filter.author:
                enhanced_query += f" author:{filter.author}"
            # Venue: use resolved venue if available
            venue = filter._resolved_venue or filter.venue
            if venue:
                enhanced_query += f" source:{venue}"

        for page in range(max_pages):
            params = {
                "engine": "google_scholar",
                "q": enhanced_query,
                "api_key": api_key,
                "num": 10,
                "start": page * 10,
            }

            # Year range: use dedicated parameters
            if filter:
                if filter.year_from:
                    params["as_ylo"] = filter.year_from
                if filter.year_to:
                    params["as_yhi"] = filter.year_to

            # Retry up to 2 times per page
            for attempt in range(2):
                try:
                    data = await self.get(self.BASE_URL, params=params)

                    # Check for quota errors
                    if data and "error" in data:
                        error_msg = data["error"].lower()
                        if "quota" in error_msg or "invalid api key" in error_msg:
                            return all_results, True

                    # No data or other error, continue to next page
                    if not data:
                        break

                    # Extract organic results
                    organic_results = data.get("organic_results", [])
                    all_results.extend(organic_results)
                    break

                except Exception:
                    # On exception, retry if attempts remaining
                    if attempt == 1:
                        # Max retries reached, continue to next page
                        break
                    continue

        return all_results, quota_reached
