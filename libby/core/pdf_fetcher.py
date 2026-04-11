"""PDF fetching orchestration with source cascade."""

import os
import logging
from pathlib import Path
from libby.models.config import LibbyConfig
from libby.models.fetch_result import FetchResult
from libby.api.crossref import CrossrefAPI
from libby.api.unpaywall import UnpaywallAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.arxiv import ArxivAPI
from libby.api.pmc import PMCAPI
from libby.api.biorxiv import BiorxivAPI
from libby.api.scihub import ScihubAPI, MANUAL_DOWNLOAD_HINT
from libby.api.scihub_selenium import ScihubDownloader
from libby.api.serpapi import SerpapiAPI, SerpapiConfirmationNeeded

logger = logging.getLogger(__name__)


class PDFFetcher:
    """Orchestrates PDF fetching through source cascade.

    Order: Crossref OA → Unpaywall → Semantic Scholar → arXiv → PMC → bioRxiv → Sci-hub → Serpapi

    Sci-hub uses fallback strategy: aiohttp first, Selenium on failure.
    """

    SOURCES = [
        "crossref_oa",
        "unpaywall",
        "semantic_scholar",
        "arxiv",
        "pmc",
        "biorxiv",
        "scihub",
        "serpapi",
    ]

    def __init__(self, config: LibbyConfig):
        self.config = config

        # Initialize API clients
        self.crossref = CrossrefAPI()
        self.unpaywall = UnpaywallAPI() if os.getenv("EMAIL") else None
        self.s2 = SemanticScholarAPI(api_key=os.getenv("S2_API_KEY"))
        self.biorxiv = BiorxivAPI()
        self.scihub = ScihubAPI(config.scihub_url)
        self.serpapi = SerpapiAPI() if os.getenv("SERPAPI_API_KEY") else None

        # Selenium downloader (lazy init, only when aiohttp fails)
        self._scihub_downloader: ScihubDownloader | None = None

        # Stateless URL builders
        self._arxiv = ArxivAPI()
        self._pmc = PMCAPI()

    def _get_selenium_downloader(self) -> ScihubDownloader:
        """Lazy init Selenium downloader."""
        if self._scihub_downloader is None:
            # Use temp directory for Selenium downloads
            temp_dir = self.config.papers_dir / "temp"
            self._scihub_downloader = ScihubDownloader(temp_dir)
        return self._scihub_downloader

    async def fetch(self, doi: str) -> FetchResult:
        """Fetch PDF through cascade.

        Returns:
            FetchResult with pdf_url, source, metadata
        """
        pdf_url = None
        source = None
        metadata = {}
        external_ids = {}
        last_error = None

        # 1. Crossref OA
        pdf_url, meta = await self.crossref.get_oa_link(doi)
        if pdf_url:
            source = "crossref_oa"
            metadata.update(meta)

        # 2. Unpaywall
        if not pdf_url and self.unpaywall:
            pdf_url, meta = await self.unpaywall.get_pdf_url(doi, os.getenv("EMAIL"))
            if pdf_url:
                source = "unpaywall"
                metadata.update(meta)

        # 3. Semantic Scholar
        if not pdf_url:
            pdf_url, meta, external_ids = await self.s2.get_pdf_url(doi)
            if pdf_url:
                source = "semantic_scholar"
                metadata.update(meta)

        # 4. arXiv (via external_ids)
        if not pdf_url and external_ids.get("ArXiv"):
            pdf_url = self._arxiv.get_pdf_url(external_ids["ArXiv"])
            source = "arxiv"

        # 5. PMC (via external_ids)
        if not pdf_url and external_ids.get("PubMedCentral"):
            pdf_url = self._pmc.get_pdf_url(external_ids["PubMedCentral"])
            source = "pmc"

        # 6. bioRxiv
        if not pdf_url:
            pdf_url = await self.biorxiv.get_pdf_url(doi)
            if pdf_url:
                source = "biorxiv"

        # 7. Sci-hub with fallback: aiohttp → Selenium
        if not pdf_url:
            # Try aiohttp first
            pdf_url, error = await self.scihub.get_pdf_url(doi)
            if pdf_url:
                source = "scihub"
                logger.info("Sci-hub via aiohttp succeeded")
            elif error:
                logger.warning(f"Sci-hub aiohttp failed: {error}")
                last_error = error

                # Fallback to Selenium
                logger.info("Trying Sci-hub via Selenium...")
                try:
                    downloader = self._get_selenium_downloader()
                    pdf_path, selenium_error = downloader.download_pdf(doi)
                    if pdf_path:
                        source = "scihub_selenium"
                        logger.info(f"Sci-hub via Selenium succeeded: {pdf_path}")
                        return FetchResult(
                            doi=doi,
                            success=True,
                            source=source,
                            pdf_url=pdf_path.as_uri(),
                            pdf_path=pdf_path,
                            metadata=metadata,
                        )
                    else:
                        logger.warning(f"Sci-hub Selenium failed: {selenium_error}")
                        last_error = selenium_error
                except Exception as e:
                    logger.warning(f"Sci-hub Selenium error: {e}")
                    last_error = str(e)

        # 8. Serpapi (raises exception for user confirmation)
        if not pdf_url and self.serpapi:
            raise SerpapiConfirmationNeeded(doi)

        if not pdf_url:
            error_msg = last_error or "No PDF found from any source"
            return FetchResult(
                doi=doi,
                success=False,
                source=None,
                pdf_url=None,
                error=error_msg,
            )

        return FetchResult(
            doi=doi,
            success=True,
            source=source,
            pdf_url=pdf_url,
            metadata=metadata,
        )

    async def fetch_from_source(self, doi: str, source: str) -> FetchResult:
        """Fetch PDF from a specific source only (skip cascade).

        Args:
            doi: DOI to fetch
            source: Source name (crossref, unpaywall, s2, arxiv, pmc, biorxiv, scihub)

        Returns:
            FetchResult with pdf_url from specified source
        """
        pdf_url = None
        metadata = {}
        source_name = None
        found_info = False

        if source == "crossref":
            pdf_url, meta = await self.crossref.get_oa_link(doi)
            if meta:
                found_info = True
            if pdf_url:
                metadata.update(meta)
                source_name = "crossref_oa"

        elif source == "unpaywall":
            if self.unpaywall:
                pdf_url, meta = await self.unpaywall.get_pdf_url(doi, os.getenv("EMAIL"))
                if meta:
                    found_info = True
                if pdf_url:
                    metadata.update(meta)
                    source_name = "unpaywall"
            else:
                return FetchResult(
                    doi=doi,
                    success=False,
                    source=None,
                    pdf_url=None,
                    error="Unpaywall unavailable: EMAIL env var not set",
                )

        elif source == "s2":
            pdf_url, meta, external_ids = await self.s2.get_pdf_url(doi)
            if meta or external_ids:
                found_info = True
            if pdf_url:
                metadata.update(meta)
                source_name = "semantic_scholar"

        elif source == "arxiv":
            _, _, external_ids = await self.s2.get_pdf_url(doi)
            if external_ids:
                found_info = True
            if external_ids.get("ArXiv"):
                pdf_url = self._arxiv.get_pdf_url(external_ids["ArXiv"])
                source_name = "arxiv"
            else:
                return FetchResult(
                    doi=doi,
                    success=False,
                    source=None,
                    pdf_url=None,
                    error="DOI found in S2 but no ArXiv ID available" if found_info else "DOI not found in Semantic Scholar",
                )

        elif source == "pmc":
            _, _, external_ids = await self.s2.get_pdf_url(doi)
            if external_ids:
                found_info = True
            if external_ids.get("PubMedCentral"):
                pdf_url = self._pmc.get_pdf_url(external_ids["PubMedCentral"])
                source_name = "pmc"
            else:
                return FetchResult(
                    doi=doi,
                    success=False,
                    source=None,
                    pdf_url=None,
                    error="DOI found in S2 but no PubMedCentral ID available" if found_info else "DOI not found in Semantic Scholar",
                )

        elif source == "biorxiv":
            if not doi.startswith("10.1101/"):
                return FetchResult(
                    doi=doi,
                    success=False,
                    source=None,
                    pdf_url=None,
                    error="Not a bioRxiv/medRxiv DOI (must start with 10.1101/)",
                )
            pdf_url = await self.biorxiv.get_pdf_url(doi)
            if pdf_url:
                source_name = "biorxiv"
                found_info = True

        elif source == "scihub":
            # Try aiohttp first, then Selenium fallback
            pdf_url, error = await self.scihub.get_pdf_url(doi)
            if pdf_url:
                source_name = "scihub"
                found_info = True
            elif error:
                # Fallback to Selenium
                try:
                    downloader = self._get_selenium_downloader()
                    pdf_path, selenium_error = downloader.download_pdf(doi)
                    if pdf_path:
                        source_name = "scihub_selenium"
                        found_info = True
                        return FetchResult(
                            doi=doi,
                            success=True,
                            source=source_name,
                            pdf_url=pdf_path.as_uri(),
                            pdf_path=pdf_path,
                            metadata=metadata,
                        )
                    else:
                        return FetchResult(
                            doi=doi,
                            success=False,
                            source=None,
                            pdf_url=None,
                            error=selenium_error,
                        )
                except Exception as e:
                    return FetchResult(
                        doi=doi,
                        success=False,
                        source=None,
                        pdf_url=None,
                        error=str(e),
                    )

        else:
            return FetchResult(
                doi=doi,
                success=False,
                source=None,
                pdf_url=None,
                error=f"Unknown source: {source}",
            )

        if not pdf_url:
            error_msg = f"DOI found in {source} but no PDF URL available" if found_info else f"DOI not found in {source} or source unavailable"
            return FetchResult(
                doi=doi,
                success=False,
                source=None,
                pdf_url=None,
                error=error_msg,
            )

        return FetchResult(
            doi=doi,
            success=True,
            source=source_name,
            pdf_url=pdf_url,
            metadata=metadata,
        )

    async def download_pdf_to_file(self, pdf_url: str, dest_path: Path) -> bool:
        """Stream download PDF to file.

        1. Stream download to temp file
        2. Validate: PDF header (%PDF)
        3. Rename temp to final on success

        Returns:
            True on success, False on failure
        """
        import aiohttp
        import aiofiles

        temp_path = dest_path.parent / f".tmp_{dest_path.name}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url) as resp:
                    if resp.status != 200:
                        return False

                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    async with aiofiles.open(temp_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)

                    async with aiofiles.open(temp_path, 'rb') as f:
                        header = await f.read(5)
                        if not header.startswith(b'%PDF'):
                            temp_path.unlink()
                            return False

                    temp_path.rename(dest_path)
                    return True

        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            return False

    async def close(self):
        """Close all API sessions."""
        await self.crossref.close()
        if self.unpaywall:
            await self.unpaywall.close()
        await self.s2.close()
        await self.biorxiv.close()
        await self.scihub.close()
        if self._scihub_downloader:
            self._scihub_downloader.close()