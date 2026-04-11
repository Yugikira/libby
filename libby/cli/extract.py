"""libby extract command."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.metadata import MetadataExtractor
from libby.core.pdf_fetcher import PDFFetcher, SerpapiConfirmationNeeded
from libby.utils.file_ops import FileHandler
from libby.utils.doi_parser import is_doi
from libby.cli.utils import read_stdin_lines, process_batch, save_failed_tasks
from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter
from libby.models.metadata import BibTeXMetadata
from libby.models.fetch_result import FetchResult

console = Console()


def run_async(coro):
    """Helper to run async functions."""
    return asyncio.run(coro)


def extract(
    input: Optional[str] = typer.Argument(None, help="DOI, title, or PDF path"),
    batch_dir: Optional[Path] = typer.Option(None, "--batch-dir", "-b", help="Directory of PDFs to process"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("bibtex", "--format", "-f", help="Output format: bibtex, json"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy PDF instead of moving"),
    ai_extract: bool = typer.Option(False, "--ai-extract", "-a", help="Use AI to extract DOI/title"),
    fetch: bool = typer.Option(False, "--fetch", help="Also download PDF for DOI inputs"),
    no_scihub: bool = typer.Option(False, "--no-scihub", help="Skip Sci-hub when fetching"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment variable check"),
):
    """Extract metadata and organize PDF files.

    With --fetch flag, also download PDF for DOI inputs.
    """
    # Environment check
    if not no_env_check:
        check_env_vars()

    # Load config
    config = load_config(config_path)

    # Initialize components
    extractor = MetadataExtractor(config)
    file_handler = FileHandler(config.papers_dir)

    # Select formatter
    if format == "json":
        formatter = JSONFormatter()
    else:
        formatter = BibTeXFormatter()

    # Gather inputs
    inputs = []
    if input:
        inputs.append(input)
    if batch_dir and batch_dir.exists():
        inputs.extend([str(p) for p in batch_dir.glob("*.pdf")])

    # Stdin input
    stdin_lines = read_stdin_lines()
    inputs.extend(stdin_lines)

    if not inputs:
        console.print("[red]No input provided. Use --help for usage.[/red]")
        raise typer.Exit(1)

    # Handle single DOI with --fetch
    if fetch and len(inputs) == 1 and is_doi(inputs[0]):
        doi = inputs[0]
        console.print(f"[green]Fetching PDF for DOI: {doi}[/green]")

        async def run_fetch_single():
            from rich.prompt import Confirm

            extractor = MetadataExtractor(config)
            fetcher = PDFFetcher(config)

            try:
                # Extract metadata first
                metadata = await extractor.extract_from_doi(doi)

                # Fetch PDF
                result = await fetcher.fetch(doi)

                if result.success:
                    # Download
                    target_dir = config.papers_dir / metadata.citekey
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_pdf = target_dir / f"{metadata.citekey}.pdf"

                    success = await fetcher.download_pdf_to_file(result.pdf_url, target_pdf)

                    if success:
                        # Save BibTeX
                        target_bib = target_dir / f"{metadata.citekey}.bib"
                        target_bib.write_text(BibTeXFormatter().format(metadata))
                        console.print(f"[green]PDF saved to: {target_pdf}[/green]")
                        console.print(f"[green]BibTeX saved to: {target_bib}[/green]")

                        # Output metadata
                        if output:
                            output.write_text(BibTeXFormatter().format(metadata))
                            console.print(f"[green]Output saved to {output}[/green]")
                        else:
                            console.print(BibTeXFormatter().format(metadata))
                    else:
                        console.print(f"[yellow]PDF download failed, but metadata extracted[/yellow]")
                        console.print(BibTeXFormatter().format(metadata))
                else:
                    console.print(f"[yellow]PDF not found: {result.error}[/yellow]")
                    console.print(f"[green]Metadata extracted anyway:[/green]")
                    console.print(BibTeXFormatter().format(metadata))

            except SerpapiConfirmationNeeded as e:
                if no_scihub:
                    console.print("[yellow]All sources failed, Sci-hub disabled by --no-scihub[/yellow]")
                elif os.getenv("SERPAPI_API_KEY"):
                    console.print(SerpapiConfirmationNeeded(e.doi).message)
                    if Confirm.ask("Use Serpapi?"):
                        fetcher.serpapi = None
                        result = await fetcher.fetch(doi)
                        if result.success:
                            target_dir = config.papers_dir / metadata.citekey
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target_pdf = target_dir / f"{metadata.citekey}.pdf"
                            await fetcher.download_pdf_to_file(result.pdf_url, target_pdf)
                else:
                    console.print("[yellow]All sources failed, no Serpapi key available[/yellow]")

            finally:
                await extractor.close()
                await fetcher.close()

        run_async(run_fetch_single())
        return

    # Process batch (normal workflow)
    console.print(f"[green]Processing {len(inputs)} input(s)...[/green]")

    async def run_extraction():
        results = await process_batch(inputs, extractor, file_handler, ai_extract, copy)
        await extractor.close()
        return results

    results = run_async(run_extraction())

    # Output results
    if results.succeeded:
        metadata_list = [
            BibTeXMetadata(**r["metadata"]) for r in results.succeeded
        ]
        output_text = formatter.format_batch(metadata_list)

        if output:
            output.write_text(output_text)
            console.print(f"[green]Output saved to {output}[/green]")
        else:
            console.print(output_text)

    # Failed tasks
    if results.failed:
        console.print(f"\n[yellow]Failed: {len(results.failed)} tasks[/yellow]")
        failed_file = Path("failed_tasks.json")
        save_failed_tasks(results, failed_file)
        console.print(f"[yellow]Failed tasks saved to: {failed_file}[/yellow]")

    # Summary
    console.print(f"\n[green]Succeeded: {len(results.succeeded)}[/green]")
    console.print(f"[red]Failed: {len(results.failed)}[/red]")

    # Exit code
    if results.failed:
        raise typer.Exit(1)