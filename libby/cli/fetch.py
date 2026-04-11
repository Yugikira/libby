"""libby fetch command."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from libby.models.config import LibbyConfig
from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.metadata import MetadataExtractor
from libby.core.pdf_fetcher import PDFFetcher, SerpapiConfirmationNeeded
from libby.utils.file_ops import FileHandler
from libby.output.bibtex import BibTeXFormatter
from libby.models.fetch_result import FetchResult

console = Console()


def fetch(
    input: Optional[str] = typer.Argument(None, help="DOI to fetch"),
    batch_file: Optional[Path] = typer.Option(None, "--batch", "-b", help="File with DOIs (one per line)"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Override papers directory"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Use specific source only (crossref, unpaywall, s2, arxiv, pmc, biorxiv, scihub)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show PDF URL without downloading"),
    no_scihub: bool = typer.Option(False, "--no-scihub", help="Skip Sci-hub source"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment check"),
):
    """Fetch PDF by DOI: extract metadata -> download PDF -> organize files.

    Output:
        ~/.lib/papers/{citekey}/{citekey}.pdf
        ~/.lib/papers/{citekey}/{citekey}.bib

    Sources (cascade order):
        crossref -> unpaywall -> s2 (Semantic Scholar) -> arxiv -> pmc -> biorxiv -> scihub

    Use --source to skip cascade and use only one source.

    Examples:
        libby fetch 10.1007/s11142-016-9368-9
        libby fetch --batch dois.txt
        libby fetch 10.1234/abc --source unpaywall
        libby fetch 10.1234/abc --dry-run
    """
    if not no_env_check:
        check_env_vars()

    config = load_config(config_path)

    if output_dir:
        config.papers_dir = output_dir

    dois = _gather_inputs(input, batch_file)

    if not dois:
        console.print("[red]No DOI provided. Use --help for usage.[/red]")
        raise typer.Exit(1)

    # Validate source option
    valid_sources = ["crossref", "unpaywall", "s2", "arxiv", "pmc", "biorxiv", "scihub"]
    if source and source.lower() not in valid_sources:
        console.print(f"[red]Invalid source '{source}'. Valid options: {', '.join(valid_sources)}[/red]")
        raise typer.Exit(1)

    async def run_fetch():
        return await _process_batch_fetch(dois, config, dry_run, no_scihub, source)

    results = asyncio.run(run_fetch())
    _display_results(results, dry_run)

    if any(not r.success for r in results):
        raise typer.Exit(1)


def _gather_inputs(input: Optional[str], batch_file: Optional[Path]) -> list:
    """Gather DOIs from arguments and batch file."""
    dois = []
    if input:
        dois.append(input)
    if batch_file and batch_file.exists():
        dois.extend([
            line.strip()
            for line in batch_file.read_text().splitlines()
            if line.strip()
        ])
    return dois


async def _process_batch_fetch(
    dois: list,
    config: LibbyConfig,
    dry_run: bool,
    no_scihub: bool,
    source: Optional[str] = None,
) -> list:
    """Process batch of DOIs.

    Args:
        source: If specified, use only this source (skip cascade)
    """

    extractor = MetadataExtractor(config)
    fetcher = PDFFetcher(config)

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

                # Step 2: Fetch PDF (with optional single source)
                progress.update(task, description=f"Downloading PDF for {doi}...")

                if source:
                    # Use single source only
                    result = await fetcher.fetch_from_source(doi, source.lower())
                else:
                    # Full cascade
                    if dry_run:
                        result = await fetcher.fetch(doi)
                        result.pdf_path = None
                        result.bib_path = None
                    else:
                        result = await fetcher.fetch(doi)

                if result.success and not dry_run:
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
                        source=None,
                        pdf_url=None,
                        error="All sources failed, Sci-hub disabled by --no-scihub",
                    ))
                elif os.getenv("SERPAPI_API_KEY"):
                    console.print(SerpapiConfirmationNeeded(e.doi).message)
                    if Confirm.ask("Use Serpapi?"):
                        # Re-create fetcher without serpapi to avoid infinite loop
                        fetcher.serpapi = None
                        result = await fetcher.fetch(doi)
                        results.append(result)
                    else:
                        results.append(FetchResult(
                            doi=doi,
                            success=False,
                            source=None,
                            pdf_url=None,
                            error="User declined Serpapi",
                        ))
                else:
                    results.append(FetchResult(
                        doi=doi,
                        success=False,
                        source=None,
                        pdf_url=None,
                        error="All sources failed, no Serpapi key available",
                    ))

            except Exception as e:
                progress.remove_task(task)
                console.print(f"[red]Error: {doi} - {e}[/red]")
                results.append(FetchResult(
                    doi=doi,
                    success=False,
                    source=None,
                    pdf_url=None,
                    error=str(e),
                ))

    await extractor.close()
    await fetcher.close()

    return results


def _display_results(results: list, dry_run: bool = False):
    """Display fetch results summary."""

    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if succeeded:
        console.print("\n[green]Successfully fetched:[/green]")
        for r in succeeded:
            if dry_run:
                console.print(f"  [green][{r.source}][/green] {r.doi} -> {r.pdf_url}")
            else:
                console.print(f"  [green][{r.source}][/green] {r.doi} -> {r.pdf_path}")

    if failed:
        console.print("\n[red]Failed:[/red]")
        for r in failed:
            console.print(f"  [red]{r.doi}[/red] - {r.error}")

    console.print(f"\n[green]Succeeded: {len(succeeded)}[/green]")
    console.print(f"[red]Failed: {len(failed)}[/red]")
