"""libby extract command."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm

from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.metadata import MetadataExtractor, SerpapiSearchNeeded
from libby.core.pdf_fetcher import PDFFetcher, SerpapiConfirmationNeeded
from libby.utils.file_ops import FileHandler
from libby.utils.doi_parser import is_doi
from libby.cli.utils import read_stdin_lines, process_batch, save_failed_tasks
from libby.cli.serpapi_policy import SerpapiPolicy, parse_serpapi_policy, SERPAPI_POLICY_HELP
from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter
from libby.models.metadata import BibTeXMetadata
from libby.models.fetch_result import FetchResult
from libby.models.result import BatchResult

console = Console()

# Separator for pipe/batch input: pdf_path|doi or pdf_path|title
INPUT_SEPARATOR = "|"


def parse_input_with_metadata(input_str: str) -> tuple[str, Optional[str], Optional[str]]:
    """Parse input that may contain PDF path with DOI or title.

    Formats:
        - "pdf_path" -> (pdf_path, None, None)
        - "pdf_path|doi" -> (pdf_path, doi, None)
        - "pdf_path|title" -> (pdf_path, None, title)

    Returns:
        (path, doi, title)
    """
    if INPUT_SEPARATOR in input_str:
        parts = input_str.split(INPUT_SEPARATOR, 1)
        path = parts[0].strip()
        metadata_part = parts[1].strip()

        if is_doi(metadata_part):
            return (path, metadata_part, None)
        else:
            return (path, None, metadata_part)
    else:
        return (input_str, None, None)


def run_async(coro):
    """Helper to run async functions."""
    return asyncio.run(coro)


def extract(
    input: Optional[str] = typer.Argument(None, help="DOI, title, or PDF path (or 'pdf_path|doi' / 'pdf_path|title')"),
    batch_dir: Optional[Path] = typer.Option(None, "--batch-dir", "-b", help="Directory of PDFs to process"),
    batch_file: Optional[Path] = typer.Option(None, "--batch", help="File with pdf_path|doi or pdf_path|title pairs (one per line)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("bibtex", "--format", "-f", help="Output format: bibtex, json"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy PDF instead of moving"),
    ai_extract: bool = typer.Option(False, "--ai-extract", "-a", help="Use AI to extract DOI/title"),
    fetch: bool = typer.Option(False, "--fetch", help="Also download PDF for DOI inputs"),
    no_scihub: bool = typer.Option(False, "--no-scihub", help="Skip Sci-hub when fetching"),
    with_doi: Optional[str] = typer.Option(None, "--with-doi", help="Provide DOI for PDF input (scanned PDFs)"),
    with_title: Optional[str] = typer.Option(None, "--with-title", help="Provide title for PDF input (scanned PDFs)"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Use specific source only (crossref, s2, serpapi)"),
    serpapi: str = typer.Option("deny", "--serpapi", help=SERPAPI_POLICY_HELP),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment variable check"),
):
    """Extract metadata and organize PDF files.

    Input types:
        - DOI: Query Crossref for metadata
        - Title: Search Crossref -> S2 -> Serpapi (cascade)
        - PDF: Extract DOI/title from first page, then get metadata
        - PDF with metadata: 'pdf_path|doi' or 'pdf_path|title' (for scanned PDFs)

    For scanned PDFs that cannot extract DOI/title:
        - Use --with-doi or --with-title for single PDF
        - Use pipe/batch input: 'pdf_path|doi' or 'pdf_path|title'

    Title search cascade:
        1. Crossref (free)
        2. Semantic Scholar (free)
        3. Serpapi (uses quota, controlled by --serpapi policy)

    --source serpapi: Direct Serpapi search (bypasses cascade and --serpapi policy).

    With --fetch flag, also download PDF for DOI inputs.
    """
    # Environment check
    if not no_env_check:
        check_env_vars()

    # Parse serpapi policy
    try:
        serpapi_policy = parse_serpapi_policy(serpapi)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Validate source option
    valid_sources = ["crossref", "s2", "serpapi"]
    if source and source.lower() not in valid_sources:
        console.print(f"[red]Invalid source '{source}'. Valid options: {', '.join(valid_sources)}[/red]")
        raise typer.Exit(1)

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

    # Validate --with-doi/--with-title usage
    if (with_doi or with_title) and input:
        input_path = Path(input)
        if not input_path.exists() or input_path.suffix.lower() != ".pdf":
            console.print("[red]--with-doi/--with-title only works with PDF file input[/red]")
            raise typer.Exit(1)

    if with_doi and with_title:
        console.print("[red]Cannot use both --with-doi and --with-title[/red]")
        raise typer.Exit(1)

    # Gather inputs
    inputs = []  # List of (input_str, doi, title) tuples

    if input:
        if with_doi:
            inputs.append((input, with_doi, None))
        elif with_title:
            inputs.append((input, None, with_title))
        else:
            path, doi, title = parse_input_with_metadata(input)
            inputs.append((path, doi, title))

    # Batch directory (PDFs without metadata)
    if batch_dir and batch_dir.exists():
        for pdf_path in batch_dir.glob("*.pdf"):
            inputs.append((str(pdf_path), None, None))

    # Batch file (pdf_path|doi or pdf_path|title pairs)
    if batch_file and batch_file.exists():
        for line in batch_file.read_text().splitlines():
            if line.strip():
                path, doi, title = parse_input_with_metadata(line.strip())
                inputs.append((path, doi, title))

    # Stdin input (supports pdf_path|doi/title format)
    stdin_lines = read_stdin_lines()
    for line in stdin_lines:
        path, doi, title = parse_input_with_metadata(line)
        inputs.append((path, doi, title))

    if not inputs:
        console.print("[red]No input provided. Use --help for usage.[/red]")
        raise typer.Exit(1)

    # Determine use_serpapi based on policy and source
    # --source serpapi bypasses policy and uses Serpapi directly
    use_serpapi_direct = source and source.lower() == "serpapi"

    # Handle --source serpapi: direct Serpapi search
    if use_serpapi_direct:
        console.print(f"[green]Processing {len(inputs)} input(s) via Serpapi...[/green]")

        async def run_extraction():
            results = await process_batch(inputs, extractor, file_handler, ai_extract, copy, use_serpapi=True)
            await extractor.close()
            return results

        results = run_async(run_extraction())

    # Handle single DOI with --fetch (input is just a DOI string)
    elif fetch and len(inputs) == 1 and is_doi(inputs[0][0]) and not Path(inputs[0][0]).exists():
        doi = inputs[0][0]
        console.print(f"[green]Fetching PDF for DOI: {doi}[/green]")

        async def run_fetch_single():
            extractor = MetadataExtractor(config)
            fetcher = PDFFetcher(config)

            try:
                # Extract metadata first
                metadata = await extractor.extract_from_doi(doi)

                # Fetch PDF
                result = await fetcher.fetch(doi, no_scihub=no_scihub)

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
                await extractor.close()
                # Handle Serpapi based on policy
                if serpapi_policy == SerpapiPolicy.deny:
                    console.print("[yellow]All sources failed. Use --serpapi ask or auto to try Serpapi.[/yellow]")
                elif serpapi_policy == SerpapiPolicy.ask:
                    if os.getenv("SERPAPI_API_KEY") or config.get_serpapi_api_key():
                        console.print(e.message)
                        if Confirm.ask("Use Serpapi?"):
                            fetcher.serpapi = None
                            result = await fetcher.fetch(doi, no_scihub=no_scihub)
                            if result.success:
                                target_dir = config.papers_dir / metadata.citekey
                                target_dir.mkdir(parents=True, exist_ok=True)
                                target_pdf = target_dir / f"{metadata.citekey}.pdf"
                                await fetcher.download_pdf_to_file(result.pdf_url, target_pdf)
                        else:
                            console.print("[yellow]User declined Serpapi[/yellow]")
                    else:
                        console.print("[yellow]All sources failed, no Serpapi key available[/yellow]")
                elif serpapi_policy == SerpapiPolicy.auto:
                    if os.getenv("SERPAPI_API_KEY") or config.get_serpapi_api_key():
                        console.print("[yellow]Trying Serpapi...[/yellow]")
                        fetcher.serpapi = None
                        result = await fetcher.fetch(doi, no_scihub=no_scihub)
                        if result.success:
                            target_dir = config.papers_dir / metadata.citekey
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target_pdf = target_dir / f"{metadata.citekey}.pdf"
                            await fetcher.download_pdf_to_file(result.pdf_url, target_pdf)
                        else:
                            console.print(f"[yellow]Serpapi also failed: {result.error}[/yellow]")
                    else:
                        console.print("[yellow]All sources failed, no Serpapi key available[/yellow]")

            finally:
                await extractor.close()
                await fetcher.close()

        run_async(run_fetch_single())
        return

    # Normal workflow: title/DOI/PDF extraction
    else:
        console.print(f"[green]Processing {len(inputs)} input(s)...[/green]")

        # Determine use_serpapi for batch
        # deny: never use Serpapi
        # ask: only valid for single input (prompt user)
        # auto: use Serpapi automatically
        single_input_mode = len(inputs) == 1
        use_serpapi_in_batch = serpapi_policy == SerpapiPolicy.auto

        async def run_extraction():
            if single_input_mode and serpapi_policy == SerpapiPolicy.ask:
                # Single input with 'ask' policy: handle SerpapiSearchNeeded with user confirmation
                input_item, provided_doi, provided_title = inputs[0]
                input_path = Path(input_item)

                try:
                    if input_path.suffix.lower() == ".pdf" and input_path.exists():
                        if provided_doi:
                            metadata = await extractor.extract_from_doi(provided_doi)
                        elif provided_title:
                            metadata = await extractor.extract_from_title(provided_title)
                        else:
                            metadata = await extractor.extract_from_pdf(input_path, use_ai=ai_extract)
                        file_handler.organize_pdf(input_path, metadata, copy=copy)

                    elif input_path.exists():
                        raise MetadataNotFoundError(f"Unsupported file type: {input_path}")

                    elif provided_doi or is_doi(input_item):
                        doi = provided_doi or input_item
                        metadata = await extractor.extract_from_doi(doi)

                    else:
                        title = provided_title or input_item
                        metadata = await extractor.extract_from_title(title)

                    await extractor.close()
                    return BatchResult(succeeded=[{
                        "input": input_item,
                        "citekey": metadata.citekey,
                        "doi": metadata.doi,
                        "metadata": metadata.to_dict(),
                    }])

                except SerpapiSearchNeeded as e:
                    await extractor.close()
                    console.print(f"\n[yellow]{e.message}[/yellow]")

                    if os.getenv("SERPAPI_API_KEY") or config.get_serpapi_api_key():
                        if Confirm.ask("Use Serpapi (Google Scholar)?"):
                            extractor2 = MetadataExtractor(config)
                            try:
                                if input_path.suffix.lower() == ".pdf" and input_path.exists():
                                    metadata = await extractor2.extract_from_title(e.title, use_serpapi=True)
                                    file_handler.organize_pdf(input_path, metadata, copy=copy)
                                else:
                                    metadata = await extractor2.extract_from_title(e.title, use_serpapi=True)
                                await extractor2.close()
                                return BatchResult(succeeded=[{
                                    "input": input_item,
                                    "citekey": metadata.citekey,
                                    "doi": metadata.doi,
                                    "metadata": metadata.to_dict(),
                                }])
                            except Exception as e2:
                                await extractor2.close()
                                return BatchResult(failed=[{
                                    "input": input_item,
                                    "error": str(e2),
                                }])
                        else:
                            return BatchResult(failed=[{
                                "input": input_item,
                                "error": "User declined Serpapi",
                            }])
                    else:
                        return BatchResult(failed=[{
                            "input": input_item,
                            "error": "Serpapi requires SERPAPI_API_KEY",
                        }])

                except Exception as e:
                    await extractor.close()
                    return BatchResult(failed=[{
                        "input": input_item,
                        "error": str(e),
                    }])

            else:
                # Batch mode or 'deny'/'auto' policy
                results = await process_batch(inputs, extractor, file_handler, ai_extract, copy, use_serpapi=use_serpapi_in_batch)
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
        # Save to ~/.lib/extract_task/
        config.extract_task_dir.mkdir(parents=True, exist_ok=True)
        failed_file = config.extract_task_dir / "failed_tasks.json"
        save_failed_tasks(results, failed_file)
        console.print(f"[yellow]Failed tasks saved to: {failed_file}[/yellow]")

    # Summary
    console.print(f"\n[green]Succeeded: {len(results.succeeded)}[/green]")
    console.print(f"[red]Failed: {len(results.failed)}[/red]")

    # Exit code
    if results.failed:
        raise typer.Exit(1)