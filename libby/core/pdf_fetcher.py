"""PDF fetching orchestration with source cascade."""

import logging
import shutil
from pathlib import Path
from libby.models.config import LibbyConfig
from libby.models.fetch_result import FetchResult
from libby.api.crossref import CrossrefAPI
from libby.api.unpaywall import UnpaywallAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.arxiv import ArxivAPI
from libby.api.pmc import PMCAPI
from libby.api.biorxiv import BiorxivAPI
from libby.api.core import CoreAPI
from libby.api.scihub import ScihubAPI, MANUAL_DOWNLOAD_HINT
from libby.api.scihub_selenium import ScihubDownloader
from libby.api.serpapi import SerpapiAPI, SerpapiConfirmationNeeded

logger = logging.getLogger(__name__)


class PDFFetcher:
    """Orchestrates PDF fetching through source cascade.

    Order: Crossref OA → Unpaywall → Semantic Scholar → CORE → arXiv → PMC → bioRxiv → Sci-hub → Serpapi

    Each source: get URL → try download → if fail, continue to next source.
    Sci-hub: aiohttp → Selenium fallback.
    """

    SOURCES = [
        "crossref_oa",
        "unpaywall",
        "semantic_scholar",
        "core",
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
        self.unpaywall = UnpaywallAPI() if config.get_email() else None
        self.s2 = SemanticScholarAPI(api_key=config.get_s2_api_key())
        self.core = CoreAPI()
        self.biorxiv = BiorxivAPI()
        self.scihub = ScihubAPI(config.scihub_url)
        self.serpapi = SerpapiAPI() if config.get_serpapi_api_key() else None

        # Selenium downloader (lazy init)
        self._scihub_downloader: ScihubDownloader | None = None

        # Stateless URL builders
        self._arxiv = ArxivAPI()
        self._pmc = PMCAPI()

    def _get_selenium_downloader(self) -> ScihubDownloader:
        """Lazy init Selenium downloader."""
        if self._scihub_downloader is None:
            temp_dir = self.config.papers_dir / "temp"
            self._scihub_downloader = ScihubDownloader(temp_dir)
        return self._scihub_downloader

    async def fetch(self, doi: str, target_path: Path | None = None) -> FetchResult:
        """Fetch PDF through cascade with download verification.

        Each source: get URL → attempt download → if fail, continue to next.

        Args:
            doi: Paper DOI
            target_path: Target PDF path (optional, creates temp if not provided)

        Returns:
            FetchResult with pdf_path if downloaded, pdf_url if URL only
        """
        metadata = {}
        external_ids = {}
        last_error = None
        last_source = None

        # Create temp path if not provided
        if target_path is None:
            temp_dir = self.config.papers_dir / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            target_path = temp_dir / f"{doi.replace('/', '_').replace(':', '_')}.pdf"

        # 1. Crossref OA
        pdf_url, meta = await self.crossref.get_oa_link(doi)
        if pdf_url:
            metadata.update(meta)
            if await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="crossref_oa",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("Crossref OA download failed, continuing cascade...")
            last_error = "Crossref OA download failed"
            last_source = "crossref_oa"

        # Get external_ids from S2 early (needed for arxiv/PMC)
        _, _, external_ids = await self.s2.get_pdf_url(doi)

        # 2. Unpaywall
        if self.unpaywall:
            pdf_url, meta = await self.unpaywall.get_pdf_url(doi, self.config.get_email())
            if pdf_url:
                metadata.update(meta)
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source="unpaywall",
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )
                logger.warning("Unpaywall download failed, continuing cascade...")
                last_error = "Unpaywall download failed"
                last_source = "unpaywall"

        # 3. Semantic Scholar
        pdf_url, meta, _ = await self.s2.get_pdf_url(doi)
        if pdf_url:
            metadata.update(meta)
            if await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="semantic_scholar",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("Semantic Scholar download failed, continuing cascade...")
            last_error = "Semantic Scholar download failed"
            last_source = "semantic_scholar"

        # 4. CORE.ac.uk (institutional repositories)
        pdf_url, meta = await self.core.get_pdf_url(doi)
        if pdf_url:
            metadata.update(meta)
            if await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="core",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("CORE download failed, continuing cascade...")
            last_error = "CORE download failed"
            last_source = "core"

        # 5. arXiv (via external_ids)
        if external_ids.get("ArXiv"):
            pdf_url = self._arxiv.get_pdf_url(external_ids["ArXiv"])
            if pdf_url and await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="arxiv",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("arXiv download failed, continuing cascade...")
            last_error = "arXiv download failed"
            last_source = "arxiv"

        # 6. PMC (via external_ids)
        if external_ids.get("PubMedCentral"):
            pdf_url = self._pmc.get_pdf_url(external_ids["PubMedCentral"])
            if pdf_url and await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="pmc",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("PMC download failed, continuing cascade...")
            last_error = "PMC download failed"
            last_source = "pmc"

        # 7. bioRxiv
        pdf_url = await self.biorxiv.get_pdf_url(doi)
        if pdf_url:
            if await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="biorxiv",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("bioRxiv download failed, continuing cascade...")
            last_error = "bioRxiv download failed"
            last_source = "biorxiv"

        # 8. Sci-hub: aiohttp → Selenium
        pdf_url, error = await self.scihub.get_pdf_url(doi)
        if pdf_url:
            if await self._try_download(pdf_url, target_path):
                return FetchResult(
                    doi=doi, success=True, source="scihub",
                    pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                )
            logger.warning("Sci-hub aiohttp download failed")

        # Sci-hub Selenium fallback
        try:
            downloader = self._get_selenium_downloader()
            pdf_path, selenium_error = downloader.download_pdf(doi)
            if pdf_path and pdf_path.exists():
                # Move to target path
                shutil.move(str(pdf_path), str(target_path))
                return FetchResult(
                    doi=doi, success=True, source="scihub_selenium",
                    pdf_url=target_path.as_uri(), pdf_path=target_path, metadata=metadata
                )
            last_error = selenium_error or "Sci-hub Selenium failed"
            last_source = "scihub"
        except Exception as e:
            logger.warning(f"Sci-hub Selenium error: {e}")
            last_error = str(e)
            last_source = "scihub"

        # 9. Serpapi (raises exception for user confirmation)
        if self.serpapi:
            raise SerpapiConfirmationNeeded(doi)

        # All sources failed
        error_msg = last_error or "No PDF found from any source"
        return FetchResult(
            doi=doi, success=False, source=last_source,
            pdf_url=None, error=error_msg, metadata=metadata
        )

    async def _try_download(self, pdf_url: str, target_path: Path) -> bool:
        """Try to download PDF from URL.

        Returns:
            True if download succeeded, False otherwise
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        return await self.download_pdf_to_file(pdf_url, target_path)

    async def fetch_from_source(self, doi: str, source: str, target_path: Path | None = None) -> FetchResult:
        """Fetch PDF from a specific source only (skip cascade).

        Args:
            doi: DOI to fetch
            source: Source name (crossref, unpaywall, s2, arxiv, pmc, biorxiv, scihub)
            target_path: Target PDF path (optional)

        Returns:
            FetchResult with pdf_url from specified source
        """
        metadata = {}
        source_name = None
        found_info = False

        if target_path is None:
            temp_dir = self.config.papers_dir / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            target_path = temp_dir / f"{doi.replace('/', '_').replace(':', '_')}.pdf"

        if source == "crossref":
            pdf_url, meta = await self.crossref.get_oa_link(doi)
            if meta:
                found_info = True
                metadata.update(meta)
            if pdf_url:
                source_name = "crossref_oa"
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        elif source == "unpaywall":
            if self.unpaywall:
                pdf_url, meta = await self.unpaywall.get_pdf_url(doi, self.config.get_email())
                if meta:
                    found_info = True
                    metadata.update(meta)
                if pdf_url:
                    source_name = "unpaywall"
                    if await self._try_download(pdf_url, target_path):
                        return FetchResult(
                            doi=doi, success=True, source=source_name,
                            pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                        )
            else:
                return FetchResult(
                    doi=doi, success=False, source=None, pdf_url=None,
                    error="Unpaywall unavailable: EMAIL env var not set"
                )

        elif source == "s2":
            pdf_url, meta, external_ids = await self.s2.get_pdf_url(doi)
            if meta or external_ids:
                found_info = True
                metadata.update(meta)
            if pdf_url:
                source_name = "semantic_scholar"
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        elif source == "core":
            pdf_url, meta = await self.core.get_pdf_url(doi)
            if meta:
                found_info = True
                metadata.update(meta)
            if pdf_url:
                source_name = "core"
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        elif source == "arxiv":
            _, _, external_ids = await self.s2.get_pdf_url(doi)
            if external_ids:
                found_info = True
            if external_ids.get("ArXiv"):
                pdf_url = self._arxiv.get_pdf_url(external_ids["ArXiv"])
                source_name = "arxiv"
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        elif source == "pmc":
            _, _, external_ids = await self.s2.get_pdf_url(doi)
            if external_ids:
                found_info = True
            if external_ids.get("PubMedCentral"):
                pdf_url = self._pmc.get_pdf_url(external_ids["PubMedCentral"])
                source_name = "pmc"
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        elif source == "biorxiv":
            if not doi.startswith("10.1101/"):
                return FetchResult(
                    doi=doi, success=False, source=None, pdf_url=None,
                    error="Not a bioRxiv/medRxiv DOI (must start with 10.1101)"
                )
            pdf_url = await self.biorxiv.get_pdf_url(doi)
            if pdf_url:
                source_name = "biorxiv"
                found_info = True
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        elif source == "scihub":
            # Try aiohttp first
            pdf_url, error = await self.scihub.get_pdf_url(doi)
            if pdf_url:
                source_name = "scihub"
                found_info = True
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

            # Selenium fallback
            try:
                downloader = self._get_selenium_downloader()
                pdf_path, selenium_error = downloader.download_pdf(doi)
                if pdf_path and pdf_path.exists():
                    shutil.move(str(pdf_path), str(target_path))
                    return FetchResult(
                        doi=doi, success=True, source="scihub_selenium",
                        pdf_url=target_path.as_uri(), pdf_path=target_path, metadata=metadata
                    )
                return FetchResult(
                    doi=doi, success=False, source=None, pdf_url=None,
                    error=selenium_error or "Sci-hub failed"
                )
            except Exception as e:
                return FetchResult(
                    doi=doi, success=False, source=None, pdf_url=None, error=str(e)
                )

        elif source == "serpapi":
            if not self.serpapi:
                return FetchResult(
                    doi=doi, success=False, source=None, pdf_url=None,
                    error="Serpapi unavailable: SERPAPI_API_KEY not set"
                )
            api_key = self.config.get_serpapi_api_key()
            if not api_key:
                return FetchResult(
                    doi=doi, success=False, source=None, pdf_url=None,
                    error="Serpapi unavailable: SERPAPI_API_KEY not set"
                )
            pdf_url = await self.serpapi.get_pdf_url(doi, api_key)
            if pdf_url:
                source_name = "serpapi"
                found_info = True
                if await self._try_download(pdf_url, target_path):
                    return FetchResult(
                        doi=doi, success=True, source=source_name,
                        pdf_url=pdf_url, pdf_path=target_path, metadata=metadata
                    )

        else:
            return FetchResult(
                doi=doi, success=False, source=None, pdf_url=None,
                error=f"Unknown source: {source}"
            )

        # No download success
        error_msg = f"DOI found in {source} but download failed" if found_info else f"DOI not found in {source}"
        return FetchResult(
            doi=doi, success=False, source=source_name, pdf_url=None,
            error=error_msg, metadata=metadata
        )

    async def download_pdf_to_file(self, pdf_url: str, dest_path: Path) -> bool:
        """Stream download PDF to file.

        Returns:
            True on success, False on failure
        """
        import aiohttp
        import aiofiles

        temp_path = dest_path.parent / f".tmp_{dest_path.name}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        logger.warning(f"Download failed: status {resp.status}")
                        return False

                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    async with aiofiles.open(temp_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)

                    # Validate PDF header
                    async with aiofiles.open(temp_path, 'rb') as f:
                        header = await f.read(5)
                        if not header.startswith(b'%PDF'):
                            logger.warning("Download failed: not a valid PDF")
                            temp_path.unlink()
                            return False

                    temp_path.rename(dest_path)
                    logger.info(f"Downloaded: {dest_path}")
                    return True

        except Exception as e:
            logger.warning(f"Download error: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    async def close(self):
        """Close all API sessions."""
        await self.crossref.close()
        if self.unpaywall:
            await self.unpaywall.close()
        await self.s2.close()
        await self.core.close()
        await self.biorxiv.close()
        await self.scihub.close()
        if self._scihub_downloader:
            self._scihub_downloader.close()