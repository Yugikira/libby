# libby fetch Design Document

**Date**: 2026-04-11
**Author**: Yugi + Claude
**Status**: Approved - Ready for Implementation

---

## 1. Project Overview

`libby fetch` is a PDF downloading subsystem that downloads open-access PDFs by DOI through a cascade of legal sources.

**Key Features:**
- One-stop command: metadata extraction + PDF download + file organization
- Cascade through 7+ OA sources in priority order
- Optional Serpapi Google Scholar (requires user confirmation)
- Configurable Sci-hub URL support
- Streaming download (memory efficient)

---

## 2. Architecture

### 2.1 Module Structure

```
libby/
├── cli/
│   ├── extract.py            # (existing) + add --fetch option
│   └── fetch.py              # libby fetch command
├── core/
│   ├── pdf_fetcher.py        # PDF cascade orchestration
│   └── metadata.py           # (existing)
├── api/
│   ├── crossref.py           # (existing) + add get_oa_link()
│   ├── unpaywall.py          # Unpaywall API client
│   ├── semantic_scholar.py   # Semantic Scholar API client
│   ├── arxiv.py              # arXiv PDF URL builder
│   ├── pmc.py                # PubMed Central PDF URL builder
│   ├── biorxiv.py            # bioRxiv/medRxiv API client
│   ├── scihub.py             # Sci-hub downloader
│   ├── serpapi.py            # Serpapi Google Scholar (optional)
│   └── base.py               # (existing)
├── utils/
│   └── file_ops.py           # (existing) + add organize_pdf_bytes()
├── models/
│   ├── config.py             # (existing) + add scihub_url
│   └── fetch_result.py       # FetchResult dataclass
└── output/
    └── bibtex.py             # (existing)
```

### 2.2 Design Principles

- **Separation of Concerns**: PDFFetcher downloads, FileHandler organizes
- **Streaming Download**: Memory-efficient, no large bytes in memory
- **Cascade Fallback**: Try sources in order, first success wins
- **User Control**: --fetch flag to trigger download, --no-scihub to skip

---

## 3. API Layer

### 3.1 Source Cascade Order

```
Crossref OA → Unpaywall → Semantic Scholar → arXiv → PMC → bioRxiv → Sci-hub → Serpapi(optional)
```

### 3.2 Crossref API (extension)

```python
# api/crossref.py
class CrossrefAPI(AsyncAPIClient):
    async def get_oa_link(self, doi: str) -> tuple[str | None, dict]:
        """Get open access PDF URL from Crossref metadata.
        
        Returns:
            (pdf_url, metadata) or (None, {})
        """
        data = await self.fetch_by_doi(doi)
        if not data:
            return None, {}
        
        # Check for open access link
        for link in data.get("link", []):
            if link.get("intended") == "text-mining" or "pdf" in link.get("content-type", ""):
                return link.get("URL"), {"title": data.get("title"), "year": data.get("year")}
        
        return None, {}
```

### 3.3 Unpaywall API

```python
# api/unpaywall.py
class UnpaywallAPI(AsyncAPIClient):
    BASE_URL = "https://api.unpaywall.org/v2"
    
    async def get_pdf_url(self, doi: str, email: str) -> tuple[str | None, dict]:
        """Get best OA PDF URL from Unpaywall.
        
        Requires EMAIL parameter. Returns None if not set.
        """
        url = f"{self.BASE_URL}/{doi}?email={email}"
        data = await self.get(url)
        
        if data.get("best_oa_location"):
            loc = data["best_oa_location"]
            return loc.get("url_for_pdf"), {
                "title": data.get("title"),
                "year": data.get("year"),
            }
        return None, {}
```

### 3.4 Semantic Scholar API

```python
# api/semantic_scholar.py
class SemanticScholarAPI(AsyncAPIClient):
    RATE_LIMIT = RateLimit(1, 1)  # Always 1 req/sec
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    async def get_pdf_url(self, doi: str) -> tuple[str | None, dict, dict]:
        """Get openAccessPdf URL + external IDs.
        
        Returns:
            (pdf_url, metadata, external_ids)
            external_ids may contain "ArXiv", "PubMedCentral" for fallback
        """
        url = f"{self.BASE_URL}/paper/DOI:{doi}"
        params = {"fields": "title,year,authors,openAccessPdf,externalIds"}
        
        data = await self.get(url, params=params)
        
        pdf_url = (data.get("openAccessPdf") or {}).get("url")
        metadata = {
            "title": data.get("title"),
            "year": data.get("year"),
        }
        external_ids = data.get("externalIds") or {}
        
        return pdf_url, metadata, external_ids
```

### 3.5 arXiv (URL builder)

```python
# api/arxiv.py
class ArxivAPI:
    """arXiv PDF URL builder (no API call needed)."""
    
    @staticmethod
    def get_pdf_url(arxiv_id: str) -> str:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
```

### 3.6 PubMed Central (URL builder)

```python
# api/pmc.py
class PMCAPI:
    """PMC PDF URL builder."""
    
    @staticmethod
    def get_pdf_url(pmcid: str) -> str:
        pmcid = pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
```

### 3.7 bioRxiv/medRxiv

```python
# api/biorxiv.py
class BiorxivAPI(AsyncAPIClient):
    BASE_URL = "https://api.biorxiv.org"
    
    async def get_pdf_url(self, doi: str) -> str | None:
        """Get PDF URL for bioRxiv/medRxiv DOIs."""
        if not doi.startswith("10.1101/"):
            return None
        
        for server in ("biorxiv", "medrxiv"):
            url = f"{self.BASE_URL}/details/{server}/{doi}"
            data = await self.get(url)
            
            if data.get("collection"):
                latest = data["collection"][-1]
                return f"https://www.{server}.org/content/{doi}v{latest.get('version', 1)}.full.pdf"
        
        return None
```

### 3.8 Sci-hub

```python
# api/scihub.py
class ScihubAPI(AsyncAPIClient):
    """Sci-hub PDF downloader."""
    
    def __init__(self, scihub_url: str = "https://sci-hub.ru"):
        self.scihub_url = scihub_url
    
    async def get_pdf_url(self, doi: str) -> str | None:
        """Get PDF URL from Sci-hub.
        
        1. Fetch Sci-hub page: {scihub_url}/{doi}
        2. Parse HTML for PDF embed URL
        3. Return direct PDF URL
        """
        html = await self.get_html(f"{self.scihub_url}/{doi}")
        pdf_url = self._parse_pdf_url(html)
        
        if pdf_url and pdf_url.startswith("//"):
            pdf_url = "https:" + pdf_url
        
        return pdf_url
    
    def _parse_pdf_url(self, html: str) -> str | None:
        """Extract PDF URL from Sci-hub HTML."""
        import re
        # Pattern for iframe/embed PDF URL
        match = re.search(r'<iframe[^>]+src=["\']([^"\']+\.pdf)["\']', html)
        if match:
            return match.group(1)
        
        # Fallback patterns
        match = re.search(r'pdfUrl\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        
        return None
```

### 3.9 Serpapi Google Scholar (Optional)

```python
# api/serpapi.py
class SerpapiAPI(AsyncAPIClient):
    BASE_URL = "https://serpapi.com/search"
    
    async def get_pdf_url(self, doi: str, api_key: str) -> str | None:
        """Search Google Scholar for PDF link via Serpapi.
        
        Requires user confirmation before use.
        """
        params = {
            "engine": "google_scholar",
            "q": doi,
            "api_key": api_key,
        }
        data = await self.get(self.BASE_URL, params=params)
        
        for result in data.get("organic_results", []):
            if "link" in result and result["link"].endswith(".pdf"):
                return result["link"]
        
        return None


class SerpapiConfirmationNeeded(Exception):
    """Raised when all sources failed and Serpapi is available."""
    def __init__(self, doi: str):
        self.doi = doi
        self.message = (
            "All free sources failed to find PDF.\n"
            "Serpapi Google Scholar is available but uses API quota.\n"
            "Do you want to try Serpapi? (y/n)"
        )
```

---

## 4. Core Layer

### 4.1 PDFFetcher

```python
# core/pdf_fetcher.py
class PDFFetcher:
    """Orchestrates PDF fetching through source cascade."""
    
    SOURCES = [
        "crossref_oa",
        "unpaywall",
        "semantic_scholar",
        "arxiv",
        "pmc",
        "biorxiv",
        "scihub",
        "serpapi",  # optional
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
```

### 4.2 FetchResult Model

```python
# models/fetch_result.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class FetchResult:
    """Result of PDF fetch operation."""
    
    doi: str
    success: bool
    source: str | None
    pdf_url: str | None
    pdf_path: Path | None = None
    bib_path: Path | None = None
    metadata: dict | None = None
    error: str | None = None
    
    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "success": self.success,
            "source": self.source,
            "pdf_url": self.pdf_url,
            "pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "bib_path": str(self.bib_path) if self.bib_path else None,
            "metadata": self.metadata,
            "error": self.error,
        }
```

### 4.3 FileHandler Extension

```python
# utils/file_ops.py (extension)
class FileHandler:
    """Organize PDF and metadata files."""
    
    def __init__(self, papers_dir: Path):
        self.papers_dir = papers_dir
    
    def organize_pdf(self, pdf_path: Path, metadata: BibTeXMetadata, copy: bool = False) -> Path:
        """(existing) Move/copy PDF from local path."""
        ...
    
    def organize_pdf_bytes(self, pdf_bytes: bytes, metadata: BibTeXMetadata) -> Path:
        """Save PDF bytes directly to target folder.
        
        Alternative for in-memory PDF content.
        """
        target_dir = self.papers_dir / metadata.citekey
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_pdf = target_dir / f"{metadata.citekey}.pdf"
        target_pdf.write_bytes(pdf_bytes)
        
        target_bib = target_dir / f"{metadata.citekey}.bib"
        target_bib.write_text(BibTeXFormatter().format(metadata))
        
        return target_dir
```

---

## 5. CLI Layer

### 5.1 `libby fetch` Command

```python
# cli/fetch.py
import asyncio
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TaskProgressColumn
from rich.prompt import Confirm

from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.metadata import MetadataExtractor
from libby.core.pdf_fetcher import PDFFetcher, SerpapiConfirmationNeeded
from libby.utils.file_ops import FileHandler
from libby.output.bibtex import BibTeXFormatter
from libby.models.fetch_result import FetchResult

console = Console()

fetch_app = typer.Typer(name="fetch", help="Download PDF with metadata extraction")


@fetch_app.command()
def fetch(
    input: str = typer.Argument(None, help="DOI to fetch"),
    batch_file: Path = typer.Option(None, "--batch", "-b", help="File with DOIs (one per line)"),
    output_dir: Path = typer.Option(None, "--output", "-o", help="Override papers directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show PDF URL without downloading"),
    no_scihub: bool = typer.Option(False, "--no-scihub", help="Skip Sci-hub source"),
    config_path: Path = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment check"),
):
    """Fetch PDF by DOI: extract metadata → download PDF → organize files.
    
    Output:
        ~/.lib/papers/{citekey}/{citekey}.pdf
        ~/.lib/papers/{citekey}/{citekey}.bib
    
    Examples:
        libby fetch 10.1007/s11142-016-9368-9
        libby fetch --batch dois.txt
        libby fetch 10.1234/abc --dry-run
    """
    if not no_env_check:
        check_env_vars()
    
    config = load_config(config_path)
    
    if output_dir:
        config.papers_dir = output_dir
    
    dois = gather_inputs(input, batch_file)
    
    if not dois:
        console.print("[red]No DOI provided. Use --help for usage.[/red]")
        raise typer.Exit(1)
    
    async def run_fetch():
        return await process_batch_fetch(dois, config, dry_run, no_scihub)
    
    results = asyncio.run(run_fetch())
    display_results(results)
    
    if any(not r.success for r in results):
        raise typer.Exit(1)


def gather_inputs(input: str | None, batch_file: Path | None) -> list[str]:
    """Gather DOIs from arguments and batch file."""
    dois = []
    if input:
        dois.append(input)
    if batch_file and batch_file.exists():
        dois.extend([l.strip() for l in batch_file.read_text().splitlines() if l.strip()])
    return dois


async def process_batch_fetch(
    dois: list[str],
    config: LibbyConfig,
    dry_run: bool,
    no_scihub: bool,
) -> list[FetchResult]:
    """Process batch of DOIs."""
    
    extractor = MetadataExtractor(config)
    fetcher = PDFFetcher(config)
    file_handler = FileHandler(config.papers_dir)
    
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        for doi in dois:
            task = progress.add_task(f"Fetching {doi}...", total=None)
            
            try:
                # Step 1: Extract metadata
                progress.update(task, description=f"Extracting metadata for {doi}...")
                metadata = await extractor.extract_from_doi(doi)
                
                # Step 2: Fetch PDF
                progress.update(task, description=f"Downloading PDF for {doi}...")
                
                if dry_run:
                    result = await fetcher.fetch(doi)
                    result.pdf_path = None
                    result.bib_path = None
                else:
                    result = await fetcher.fetch(doi)
                    
                    if result.success:
                        # Step 3: Download to target location
                        target_dir = config.papers_dir / metadata.citekey
                        target_dir.mkdir(parents=True, exist_ok=True)
                        target_pdf = target_dir / f"{metadata.citekey}.pdf"
                        
                        success = await fetcher.download_pdf_to_file(result.pdf_url, target_pdf)
                        
                        if success:
                            # Step 4: Save BibTeX
                            target_bib = target_dir / f"{metadata.citekey}.bib"
                            target_bib.write_text(BibTeXFormatter().format(metadata))
                            
                            result.pdf_path = target_pdf
                            result.bib_path = target_bib
                            result.metadata = metadata.to_dict()
                        else:
                            result.success = False
                            result.error = "Download failed"
                
                progress.update(task, description=f"[green]Done: {metadata.citekey}[/green]")
                progress.remove_task(task)
                results.append(result)
            
            except SerpapiConfirmationNeeded as e:
                progress.remove_task(task)
                
                console.print(f"\n[yellow]DOI {doi}: All free sources failed[/yellow]")
                
                if no_scihub:
                    results.append(FetchResult(
                        doi=doi,
                        success=False,
                        error="All sources failed, Sci-hub disabled by --no-scihub",
                    ))
                else:
                    console.print(SerpapiConfirmationNeeded(e.doi).message)
                    if Confirm.ask("Use Serpapi?"):
                        result = await fetcher.try_serpapi(e.doi)
                        if result.success:
                            # Download and organize...
                            results.append(result)
                        else:
                            results.append(FetchResult(
                                doi=doi,
                                success=False,
                                error="Serpapi failed",
                            ))
                    else:
                        results.append(FetchResult(
                            doi=doi,
                            success=False,
                            error="User declined Serpapi",
                        ))
            
            except Exception as e:
                progress.remove_task(task)
                console.print(f"[red]Error: {doi} - {e}[/red]")
                results.append(FetchResult(
                    doi=doi,
                    success=False,
                    error=str(e),
                ))
    
    await extractor.close()
    await fetcher.close()
    
    return results


def display_results(results: list[FetchResult]):
    """Display fetch results summary."""
    
    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    if succeeded:
        console.print("\n[green]Successfully fetched:[/green]")
        for r in succeeded:
            console.print(f"  [green][{r.source}][/green] {r.doi} → {r.pdf_path}")
    
    if failed:
        console.print("\n[red]Failed:[/red]")
        for r in failed:
            console.print(f"  [red]{r.doi}[/red] - {r.error}")
    
    console.print(f"\n[green]Succeeded: {len(succeeded)}[/green]")
    console.print(f"[red]Failed: {len(failed)}[/red]")
```

### 5.2 `libby extract --fetch` Integration

```python
# cli/extract.py (modification)

@extract_app.command()
def extract(
    input: str = typer.Argument(None, help="DOI, title, or PDF path"),
    fetch: bool = typer.Option(False, "--fetch", "-f", help="Also download PDF"),
    # ... other existing options
):
    """Extract metadata, optionally fetch PDF."""
    
    # ... existing logic for metadata extraction
    
    if fetch and is_doi(input):
        # Run fetch workflow
        result = await run_fetch_single(input, config)
        if result.success:
            console.print(f"[green]PDF saved to: {result.pdf_path}[/green]")
        else:
            console.print(f"[yellow]PDF download failed: {result.error}[/yellow]")
```

---

## 6. Configuration

### 6.1 Config Model Extension

```python
# models/config.py
@dataclass
class LibbyConfig:
    papers_dir: Path = Path.home() / ".lib" / "papers"
    citekey: CitekeyConfig = field(default_factory=CitekeyConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    ai_extractor: AIExtractorConfig = field(default_factory=AIExtractorConfig)
    
    # New for fetch
    scihub_url: str = "https://sci-hub.ru"
    pdf_max_size: int = 50 * 1024 * 1024  # 50 MB
```

### 6.2 Environment Variables

| Variable | Purpose | If Missing |
|----------|---------|------------|
| `EMAIL` | Unpaywall access | Skip Unpaywall |
| `S2_API_KEY` | Semantic Scholar | 1 req/sec (same as with key) |
| `SERPAPI_API_KEY` | Serpapi Google Scholar | Skip Serpapi, use scholarly fallback |
| `DEEPSEEK_API_KEY` | AI Extractor | Skip AI extraction |

---

## 7. Testing

### 7.1 Test Fixtures

- DOI: `10.1007/s11142-016-9368-9` (has OA version)
- DOI: `10.1038/s41586-020-2649-2` (Nature, may need Sci-hub)

### 7.2 Unit Tests

| Module | Tests |
|--------|-------|
| `test_unpaywall.py` | Mock API, PDF URL extraction |
| `test_semantic_scholar.py` | Mock API, openAccessPdf + externalIds |
| `test_arxiv.py` | URL building |
| `test_pmc.py` | URL building |
| `test_biorxiv.py` | Mock API, bioRxiv DOI handling |
| `test_scihub.py` | Mock HTML, PDF URL parsing |
| `test_pdf_fetcher.py` | Cascade order, source selection |
| `test_file_ops.py` | organize_pdf_bytes, file organization |

### 7.3 Integration Tests

- `test_fetch_cli.py`: CLI command, dry-run, batch processing
- `test_fetch_real.py`: Real API calls (marked `@pytest.mark.integration`)

---

## 8. Error Handling

| Error Type | Handling |
|------------|----------|
| 404 Not Found | Return None, try next source |
| 429 Rate Limited | Wait and retry (per API limit) |
| 500/503 Server Error | Retry up to 3 times |
| Invalid PDF | Delete temp file, return False |
| Serpapi Confirmation | Pause and ask user |

---

## 9. Future Considerations

- **Proxy support**: For users behind corporate proxies
- **Download resume**: For large files with interrupted downloads
- **Mirror selection**: Multiple Sci-hub mirrors with auto-failover
- **Institutional access**: Integration with university proxy/VPN
