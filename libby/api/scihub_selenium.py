"""Sci-hub PDF downloader using Selenium WebDriver."""

import re
import time
import logging
from pathlib import Path
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

# Manual download instructions for user
MANUAL_DOWNLOAD_HINT = "Manual download: Open {scihub_url}/{doi} in browser"

# Sci-Hub mirrors in priority order
SCIHUB_MIRRORS = [
    "https://sci-hub.ru",
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.sg",
]


class ScihubDownloader:
    """Sci-hub PDF downloader using Selenium.

    Uses real Chrome browser to handle JavaScript and anti-bot measures.

    WARNING: Sci-hub operates in a legal gray area. Use with caution.
    """

    def __init__(self, download_dir: Optional[Path] = None):
        # Use temp directory for downloads, will be moved by caller
        self.download_dir = download_dir or Path.home() / ".lib" / "temp"
        self.driver: Optional[webdriver.Chrome] = None

    def _setup_driver(self) -> webdriver.Chrome:
        """Configure Chrome WebDriver with anti-bot measures."""
        chrome_options = Options()

        # Disable automation detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Set download directory
        self.download_dir.mkdir(parents=True, exist_ok=True)
        prefs = {
            "download.default_directory": str(self.download_dir.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Set User-Agent
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(options=chrome_options)

        # Hide webdriver property via CDP
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        return driver

    def get_pdf_url(self, doi: str, timeout: int = 30) -> tuple[str | None, str | None]:
        """Get PDF URL from Sci-hub using Selenium.

        Args:
            doi: Paper DOI
            timeout: Page load timeout in seconds

        Returns:
            (pdf_url, error_message) - pdf_url if found, error_message if failed
        """
        try:
            if not self.driver:
                self.driver = self._setup_driver()
        except WebDriverException as e:
            return None, f"Failed to init Chrome driver: {e}. Chrome browser required."

        for mirror in SCIHUB_MIRRORS:
            url = f"{mirror}/{doi}"
            try:
                logger.info(f"Trying: {url}")
                self.driver.get(url)

                # Wait for page load
                time.sleep(3)

                current_url = self.driver.current_url
                logger.debug(f"Current URL: {current_url}")

                # Try to find PDF link via <a> tags
                pdf_links = self.driver.find_elements(By.TAG_NAME, "a")
                for link in pdf_links:
                    href = link.get_attribute("href")
                    if href and (".pdf" in href.lower() or "/storage/" in href.lower()):
                        logger.info(f"Found PDF link via <a>: {href}")
                        return href, None

                # Try JavaScript query for all links
                all_links = self.driver.execute_script("""
                    var links = document.querySelectorAll('a[href]');
                    var result = [];
                    for (var i = 0; i < links.length; i++) {
                        result.push(links[i].href);
                    }
                    return result;
                """)
                for link in all_links:
                    if ".pdf" in link.lower() or "/storage/" in link.lower():
                        logger.info(f"Found PDF link via JS: {link}")
                        return link, None

                # Check if page itself is PDF
                if current_url.endswith(".pdf"):
                    logger.info(f"Page is PDF: {current_url}")
                    return current_url, None

            except TimeoutException:
                logger.warning(f"Timeout accessing {url}")
                continue
            except Exception as e:
                logger.warning(f"Error accessing {url}: {e}")
                continue

        return None, f"No PDF found. {MANUAL_DOWNLOAD_HINT.format(scihub_url=SCIHUB_MIRRORS[0], doi=doi)}"

    def download_pdf(self, doi: str, output_path: Optional[Path] = None) -> tuple[Path | None, str | None]:
        """Download PDF from Sci-hub.

        Args:
            doi: Paper DOI
            output_path: Output file path (optional, defaults to temp location)

        Returns:
            (file_path, error_message) - file_path if downloaded, error_message if failed
        """
        if output_path is None:
            # Use temp directory with DOI-based filename
            doi_part = doi.replace("/", "_").replace(":", "_")
            output_path = self.download_dir / f"{doi_part}.pdf"

        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Get PDF URL first
        pdf_url, error = self.get_pdf_url(doi)
        if not pdf_url:
            return None, error

        try:
            # Navigate to PDF URL
            self.driver.get(pdf_url)
            time.sleep(2)

            # Use fetch API to download
            download_script = f"""
            (async () => {{
                const response = await fetch('{pdf_url}');
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = '{output_path.name}';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                return blob.size;
            }})()
            """

            result = self.driver.execute_script(download_script)
            logger.debug(f"Triggered download, blob size: {result}")

            # Wait for download to complete
            time.sleep(5)

            # Check if file exists
            if output_path.exists():
                logger.info(f"Downloaded: {output_path} ({output_path.stat().st_size} bytes)")
                return output_path, None

            # Check Downloads folder
            downloads_dir = Path.home() / "Downloads"
            downloaded_file = downloads_dir / output_path.name
            if downloaded_file.exists():
                import shutil
                shutil.copy(downloaded_file, output_path)
                logger.info(f"Copied from Downloads: {output_path}")
                return output_path, None

            return None, f"Download failed - file not found at {output_path}"

        except Exception as e:
            return None, f"Download error: {e}"

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.debug("Browser closed")