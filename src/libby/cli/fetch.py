"""libby fetch command."""

import asyncio
import json
import os
import shutil
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
from libby.output.bibtex import BibTeXFormatter
from libby.models.fetch_result import FetchResult
from libby.cli.utils import read_stdin_lines
from libby.cli.serpapi_policy import SerpapiPolicy, parse_serpapi_policy, SERPAPI_POLICY_HELP

console = Console()


def fetch(
    input: Optional[str] = typer.Argument(None, help="DOI to fetch"),
    batch_file: Optional[Path] = typer.Option(None, "--batch", "-b", help="File with DOIs (one per line)"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Override papers directory"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Use specific source only (crossref, unpaywall, s2, core, arxiv, pmc, biorxiv, scihub, serpapi)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show PDF URL without downloading"),
    no_scihub: bool = typer.Option(False, "--no-scihub", help="Skip Sci-hub source"),
    serpapi: str = typer.Option("deny", "--serpapi", help=SERPAPI_POLICY_HELP),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment check"),
):
    """Fetch PDF by DOI: extract metadata -> download PDF -> organize files.

    Output:
        ~/.lib/papers/{citekey}/{citekey}.pdf
        ~/.lib/papers/{citekey}/{citekey}.bib

    Sources (cascade order):
        crossref -> unpaywall -> s2 -> core -> arxiv -> pmc -> biorxiv -> scihub

    Each source: get URL -> try download -> if fail, continue to next.
    Sci-hub: aiohttp -> Selenium fallback if blocked.

    --serpapi policy (when cascade reaches Serpapi):
        - deny: Do not use Serpapi (default)
        - ask: Prompt user for confirmation
        - auto: Auto-use Serpapi without confirmation

    --source serpapi: Bypass cascade and policy, use Serpapi directly.

    Examples:
        libby fetch 10.1007/s11142-016-9368-9
        libby fetch --batch dois.txt
        cat dois.txt | libby fetch
        libby fetch 10.1234/abc --source unpaywall
        libby fetch 10.1234/abc --source scihub
        libby fetch 10.1234/abc --dry-run
        libby fetch 10.1234/abc --serpapi auto
    """
    if not no_env_check:
        check_env_vars()

    # Parse serpapi policy
    try:
        serpapi_policy = parse_serpapi_policy(serpapi)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    config = load_config(config_path)

    dois = _gather_inputs(input, batch_file)

    if not dois:
        console.print("[red]No DOI provided. Use --help for usage.[/red]")
        raise typer.Exit(1)

    # Validate source option
    valid_sources = ["crossref", "unpaywall", "s2", "core", "arxiv", "pmc", "biorxiv", "scihub", "serpapi"]
    if source and source.lower() not in valid_sources:
        console.print(f"[red]Invalid source '{source}'. Valid options: {', '.join(valid_sources)}[/red]")
        raise typer.Exit(1)

    async def run_fetch():
        return await _process_batch_fetch(dois, config, dry_run, no_scihub, source, output_dir, serpapi_policy)

    results = asyncio.run(run_fetch())
    _display_results(results, dry_run)

    if any(not r.success for r in results):
        raise typer.Exit(1)


def _gather_inputs(input: Optional[str], batch_file: Optional[Path]) -> list:
    """Gather DOIs from arguments, batch file, and stdin."""
    dois = []
    if input:
        dois.append(input)
    if batch_file and batch_file.exists():
        dois.extend([
            line.strip()
            for line in batch_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ])
    # Stdin pipeline input
    stdin_lines = read_stdin_lines()
    dois.extend(stdin_lines)
    return dois


async def _process_batch_fetch(
    dois: list,
    config: LibbyConfig,
    dry_run: bool,
    no_scihub: bool,
    source: Optional[str] = None,
    output_dir: Optional[Path] = None,
    serpapi_policy: SerpapiPolicy = SerpapiPolicy.deny,
) -> list:
    """Process batch of DOIs.

    Args:
        source: If specified, use only this source (skip cascade)
        output_dir: Override papers directory (optional)
        serpapi_policy: Policy for Serpapi usage (deny, ask, auto)
    """

    extractor = MetadataExtractor(config)
    fetcher = PDFFetcher(config)

    # Use output_dir if provided, otherwise config.papers_dir
    papers_dir = output_dir or config.papers_dir

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

                # Step 2: Determine target path
                target_dir = papers_dir / metadata.citekey
                target_dir.mkdir(parents=True, exist_ok=True)
                target_pdf = target_dir / f"{metadata.citekey}.pdf"

                # Step 3: Fetch PDF (fetcher handles download internally)
                progress.update(task, description=f"Downloading PDF for {doi}...")

                if source:
                    result = await fetcher.fetch_from_source(doi, source.lower(), target_pdf)
                else:
                    if dry_run:
                        # Dry run: just get URL, don't download
                        result = await fetcher.fetch(doi, no_scihub=no_scihub)
                        result.pdf_path = None
                    else:
                        result = await fetcher.fetch(doi, target_pdf, no_scihub=no_scihub)

                # Step 4: Organize files (always save bib, save attempts on failure)
                target_bib = target_dir / f"{metadata.citekey}.bib"
                target_bib.write_text(BibTeXFormatter().format(metadata), encoding="utf-8")

                if result.success and not dry_run:
                    # PDF already downloaded by fetcher to target_pdf
                    result.pdf_path = target_pdf
                    result.bib_path = target_bib
                    result.metadata = metadata.to_dict()

                    progress.update(task, description=f"[green]Done: {metadata.citekey}[/green]")
                else:
                    # Save source attempts JSON on failure
                    if result.source_attempts:
                        attempts_file = target_dir / f"{metadata.citekey}_attempts.json"
                        attempts_data = {
                            "doi": doi,
                            "citekey": metadata.citekey,
                            "attempts": result.source_attempts,
                            "found_urls": [a for a in result.source_attempts if a.get("url")],
                        }
                        attempts_file.write_text(json.dumps(attempts_data, indent=2, ensure_ascii=False), encoding="utf-8")
                        console.print(f"[yellow]Saved attempt log: {attempts_file}[/yellow]")

                    result.bib_path = target_bib
                    result.metadata = metadata.to_dict()
                    progress.update(task, description=f"[red]Failed: {metadata.citekey}[/red]")

                progress.remove_task(task)
                results.append(result)

            except SerpapiConfirmationNeeded as e:
                progress.remove_task(task)

                # Save bib file first (metadata already extracted)
                target_dir = papers_dir / metadata.citekey
                target_dir.mkdir(parents=True, exist_ok=True)
                target_bib = target_dir / f"{metadata.citekey}.bib"
                target_bib.write_text(BibTeXFormatter().format(metadata), encoding="utf-8")

                # Save source attempts JSON
                if e.source_attempts:
                    attempts_file = target_dir / f"{metadata.citekey}_attempts.json"
                    attempts_data = {
                        "doi": doi,
                        "citekey": metadata.citekey,
                        "attempts": e.source_attempts,
                        "found_urls": [a for a in e.source_attempts if a.get("url")],
                    }
                    attempts_file.write_text(json.dumps(attempts_data, indent=2, ensure_ascii=False), encoding="utf-8")

                console.print(f"\n[yellow]DOI {doi}: All free sources failed[/yellow]")
                console.print(e.message)

                # Handle based on serpapi_policy
                if no_scihub:
                    results.append(FetchResult(
                        doi=doi,
                        success=False,
                        source=None,
                        pdf_url=None,
                        error="All sources failed, Sci-hub disabled by --no-scihub",
                        source_attempts=e.source_attempts,
                        bib_path=target_bib,
                        metadata=metadata.to_dict(),
                    ))
                elif serpapi_policy == SerpapiPolicy.deny:
                    results.append(FetchResult(
                        doi=doi,
                        success=False,
                        source=None,
                        pdf_url=None,
                        error="All sources failed. Use --serpapi ask or auto to try Serpapi.",
                        source_attempts=e.source_attempts,
                        bib_path=target_bib,
                        metadata=metadata.to_dict(),
                    ))
                elif serpapi_policy == SerpapiPolicy.ask:
                    if os.getenv("SERPAPI_API_KEY") or config.get_serpapi_api_key():
                        console.print(e.message)
                        if Confirm.ask("Use Serpapi?"):
                            fetcher.serpapi = None
                            # Use temp path for Serpapi result
                            result = await fetcher.fetch(doi)
                            if result.success and result.pdf_path:
                                # Move to target location
                                target_pdf = target_dir / f"{metadata.citekey}.pdf"
                                shutil.move(str(result.pdf_path), str(target_pdf))
                                result.pdf_path = target_pdf
                                result.bib_path = target_bib
                            else:
                                result.bib_path = target_bib
                            results.append(result)
                        else:
                            results.append(FetchResult(
                                doi=doi,
                                success=False,
                                source=None,
                                pdf_url=None,
                                error="User declined Serpapi",
                                source_attempts=e.source_attempts,
                                bib_path=target_bib,
                                metadata=metadata.to_dict(),
                            ))
                    else:
                        results.append(FetchResult(
                            doi=doi,
                            success=False,
                            source=None,
                            pdf_url=None,
                            error="All sources failed, no Serpapi key available",
                            source_attempts=e.source_attempts,
                            bib_path=target_bib,
                            metadata=metadata.to_dict(),
                        ))
                elif serpapi_policy == SerpapiPolicy.auto:
                    if os.getenv("SERPAPI_API_KEY") or config.get_serpapi_api_key():
                        console.print("[yellow]Trying Serpapi...[/yellow]")
                        fetcher.serpapi = None
                        result = await fetcher.fetch(doi)
                        if result.success and result.pdf_path:
                            target_pdf = target_dir / f"{metadata.citekey}.pdf"
                            shutil.move(str(result.pdf_path), str(target_pdf))
                            result.pdf_path = target_pdf
                            result.bib_path = target_bib
                        else:
                            result.bib_path = target_bib
                            console.print(f"[yellow]Serpapi also failed: {result.error}[/yellow]")
                        results.append(result)
                    else:
                        results.append(FetchResult(
                            doi=doi,
                            success=False,
                            source=None,
                            pdf_url=None,
                            error="All sources failed, no Serpapi key available",
                            source_attempts=e.source_attempts,
                            bib_path=target_bib,
                            metadata=metadata.to_dict(),
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
                console.print(f"  [green][{r.source}][/green] {r.doi} -> {r.pdf_url or 'N/A'}")
            else:
                console.print(f"  [green][{r.source}][/green] {r.doi} -> {r.pdf_path or 'N/A'}")

    if failed:
        console.print("\n[red]Failed:[/red]")
        for r in failed:
            console.print(f"  [red]{r.doi}[/red] - {r.error}")
            # Show found URLs if available
            if r.source_attempts:
                found_urls = [a for a in r.source_attempts if a.get("url")]
                if found_urls:
                    console.print("  [yellow]PDF URLs found (but blocked):[/yellow]")
                    for a in found_urls:
                        console.print(f"    [yellow]{a['source']}:[/yellow] {a['url']}")
            if r.bib_path:
                console.print(f"  [blue]BibTeX saved:[/blue] {r.bib_path}")

    console.print(f"\n[green]Succeeded: {len(succeeded)}[/green]")
    console.print(f"[red]Failed: {len(failed)}[/red]")