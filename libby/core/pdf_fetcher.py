"""PDF fetching orchestration with source cascade."""

import os
from pathlib import Path
from libby.models.config import LibbyConfig
from libby.models.fetch_result import FetchResult
from libby.api.crossref import CrossrefAPI
from libby.api.unpaywall import UnpaywallAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.arxiv import ArxivAPI
from libby.api.pmc import PMCAPI
from libby.api.biorxiv import BiorxivAPI
from libby.api.scihub import ScihubAPI
from libby.api.serpapi import SerpapiAPI, SerpapiConfirmationNeeded


class PDFFetcher:
    """Orchestrates PDF fetching through source cascade.

    Order: Crossref OA → Unpaywall → Semantic Scholar → arXiv → PMC → bioRxiv → Sci-hub → Serpapi
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

        # Stateless URL builders
        self._arxiv = ArxivAPI()
        self._pmc = PMCAPI()

    async def fetch(self, doi: str) -> FetchResult:
        """Fetch PDF through cascade.

        Returns:
            FetchResult with pdf_url, source, metadata
        """
        pdf_url = None
        source = None
        metadata = {}
        external_ids = {}

        # 1. Crossref OA
        if not pdf_url:
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

        # 7. Sci-hub
        if not pdf_url:
            pdf_url = await self.scihub.get_pdf_url(doi)
            if pdf_url:
                source = "scihub"

        # 8. Serpapi (raises exception for user confirmation)
        if not pdf_url and self.serpapi:
            raise SerpapiConfirmationNeeded(doi)

        if not pdf_url:
            return FetchResult(
                doi=doi,
                success=False,
                source=None,
                pdf_url=None,
                error="No PDF found from any source",
            )

        return FetchResult(
            doi=doi,
            success=True,
            source=source,
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

                    # Stream download
                    async with aiofiles.open(temp_path, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)

                    # Validate PDF header
                    async with aiofiles.open(temp_path, 'rb') as f:
                        header = await f.read(5)
                        if not header.startswith(b'%PDF'):
                            temp_path.unlink()
                            return False

                    # Rename to final
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
