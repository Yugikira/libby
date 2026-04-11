"""libby extract command."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.metadata import MetadataExtractor
from libby.utils.file_ops import FileHandler
from libby.cli.utils import read_stdin_lines, process_batch, save_failed_tasks
from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter
from libby.models.metadata import BibTeXMetadata

console = Console()


def run_async(coro):
    """Helper to run async functions."""
    return asyncio.run(coro)


def extract(
    input: str = typer.Argument(None, help="DOI, title, or PDF path"),
    batch_dir: Path = typer.Option(None, "--batch-dir", "-b", help="Directory of PDFs to process"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("bibtex", "--format", "-f", help="Output format: bibtex, json"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy PDF instead of moving"),
    ai_extract: bool = typer.Option(False, "--ai-extract", "-a", help="Use AI to extract DOI/title"),
    config_path: Path = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment variable check"),
):
    """Extract metadata and organize PDF files."""
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

    # Process batch
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