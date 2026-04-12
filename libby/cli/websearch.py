"""libby websearch command."""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.websearch import WebSearcher
from libby.core.metadata import MetadataExtractor
from libby.core.pdf_fetcher import PDFFetcher
from libby.models.search_filter import SearchFilter
from libby.models.search_result import SearchResults
from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter
from libby.utils.doi_parser import is_doi

console = Console()


def websearch(
    query: Optional[str] = typer.Argument(None, help="Search keywords or DOI"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    format: str = typer.Option("bibtex", "--format", "-f", help="Output format: bibtex, json"),
    limit: int = typer.Option(50, "--limit", "-l", help="Results per source"),
    year_from: Optional[int] = typer.Option(None, "--year-from", help="Start year filter"),
    year_to: Optional[int] = typer.Option(None, "--year-to", help="End year filter"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Author name filter"),
    venue: Optional[str] = typer.Option(None, "--venue", help="Journal/conference filter"),
    issn: Optional[str] = typer.Option(None, "--issn", help="ISSN filter"),
    source: Optional[str] = typer.Option(
        None, "--source", "-s",
        help="Use specific source only (crossref, semantic_scholar, scholarly, serpapi)"
    ),
    no_serpapi: bool = typer.Option(False, "--no-serpapi", help="Skip Serpapi search"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path"),
    no_env_check: bool = typer.Option(False, "--no-env-check", help="Skip environment check"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not save results to file"),
):
    """Search academic databases for scholarly papers.

    DOI input triggers fetch -> extract fallback workflow.

    Sources: Crossref, Semantic Scholar, Scholarly, Serpapi (optional)

    Default output: ~/.lib/papers/search_results/yymmdd_{keywords}.bib

    Examples:
        libby websearch "machine learning"
        libby websearch 10.1234/test
        libby websearch "AI" --year-from 2020 --author Smith --venue Nature
        libby websearch "corporate site visit" --format json --output results.json
        libby websearch "deep learning" --source crossref
        libby websearch "neural networks" --source semantic_scholar
    """
    # Environment check
    if not no_env_check:
        check_env_vars()

    # Load config
    config = load_config(config_path)

    # No query provided
    if not query:
        console.print("[red]No input provided. Use --help for usage.[/red]")
        raise typer.Exit(1)

    # DOI fallback: fetch -> extract workflow
    if is_doi(query):
        console.print(f"[yellow]Input detected as DOI: {query}[/yellow]")
        console.print("[yellow]Switching to fetch -> extract workflow...[/yellow]")
        _handle_doi_fallback(query, config, output, format)
        return

    # Build search filter
    search_filter = SearchFilter(
        year_from=year_from,
        year_to=year_to,
        author=author,
        venue=venue,
        issn=issn,
    )

    # Execute search
    async def run_search():
        searcher = WebSearcher(config)
        try:
            # Convert source string to list
            sources_list = [source] if source else None
            results = await searcher.search(
                query,
                filter=search_filter,
                limit=limit,
                skip_serpapi=no_serpapi,
                sources=sources_list,
            )
            return results
        finally:
            await searcher.close()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Searching for '{query}'...", total=None)
        results = asyncio.run(run_search())
        progress.update(task, description="[green]Search completed[/green]")
        progress.remove_task(task)

    # Display results (summary: first 3 + last 3)
    _display_results_summary(results, query)

    # Output to file
    if not no_save:
        if output:
            _save_output(results, output, format, config)
            console.print(f"[green]Output saved to {output}[/green]")
        else:
            # Default output path
            default_output = _get_default_output_path(query, config)
            _save_output(results, default_output, format, config)
            console.print(f"[green]Output saved to {default_output}[/green]")


def _handle_doi_fallback(doi: str, config, output: Optional[Path], format: str):
    """Handle DOI input with fetch -> extract fallback."""
    async def run_fallback():
        extractor = MetadataExtractor(config)
        fetcher = PDFFetcher(config)

        try:
            # Extract metadata
            metadata = await extractor.extract_from_doi(doi)

            # Try to fetch PDF (optional, just warn if fails)
            result = await fetcher.fetch(doi)

            if result.success:
                console.print(f"[green]PDF found: {result.pdf_url}[/green]")
            else:
                console.print(f"[yellow]PDF not found: {result.error}[/yellow]")

            # Output metadata
            if format == "json":
                formatter = JSONFormatter()
                output_text = formatter.format(metadata)
            else:
                formatter = BibTeXFormatter()
                output_text = formatter.format(metadata)

            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(output_text)
                console.print(f"[green]Metadata saved to {output}[/green]")
            else:
                console.print("\n[green]Metadata:[/green]")
                console.print(output_text)

        except Exception as e:
            console.print(f"[red]Error extracting metadata: {e}[/red]")
            raise typer.Exit(1)

        finally:
            await extractor.close()
            await fetcher.close()

    asyncio.run(run_fallback())


def _display_results_summary(results: SearchResults, query: str):
    """Display search results summary (first 3 + last 3)."""
    if not results.results:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        console.print(f"[yellow]Sources used: {', '.join(results.sources_used)}[/yellow]")
        return

    total = len(results.results)

    # Create table
    table = Table(title=f"Search Results for '{query}' (showing {min(6, total)} of {total})")
    table.add_column("#", style="white", width=4)
    table.add_column("Title", style="cyan", max_width=40)
    table.add_column("Author", style="green", max_width=20)
    table.add_column("Year", style="yellow")
    table.add_column("Journal", style="blue", max_width=25)
    table.add_column("DOI", style="magenta", max_width=20)

    # Show first 3 results
    for i, result in enumerate(results.results[:3], 1):
        table.add_row(
            str(i),
            _truncate(result.title, 40),
            _truncate(", ".join(result.author[:2]) if result.author else "-", 20),
            str(result.year) if result.year else "-",
            _truncate(result.journal, 25),
            _truncate(result.doi, 20),
        )

    # Show ellipsis if more than 6 results
    if total > 6:
        table.add_row("...", "...", "...", "...", "...", "...")

    # Show last 3 results
    if total > 3:
        for i, result in enumerate(results.results[-3:], total - 2):
            table.add_row(
                str(i),
                _truncate(result.title, 40),
                _truncate(", ".join(result.author[:2]) if result.author else "-", 20),
                str(result.year) if result.year else "-",
                _truncate(result.journal, 25),
                _truncate(result.doi, 20),
            )

    console.print(table)

    # Summary
    console.print(f"\n[green]Total: {total} results[/green]")
    console.print(f"[blue]Sources: {', '.join(results.sources_used)}[/blue]")


def _truncate(text: Optional[str], max_len: int) -> str:
    """Truncate text to max_len characters."""
    if not text:
        return "-"
    if len(text) > max_len:
        return text[:max_len - 3] + "..."
    return text


def _get_default_output_path(query: str, config) -> Path:
    """Generate default output path.

    Format: ~/.lib/papers/search_results/yymmdd_{keywords}.bib

    Args:
        query: Search query
        config: LibbyConfig

    Returns:
        Default output file path
    """
    # Base directory
    base_dir = config.papers_dir / "search_results"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Date prefix
    date_str = datetime.now().strftime("%y%m%d")

    # Keywords (first 3 words, cleaned)
    keywords = query.split()[:3]
    keyword_str = "_".join(keywords).lower()
    # Remove invalid characters
    keyword_str = re.sub(r'[<>:"/\\|?*]', '_', keyword_str)
    # Limit length
    if len(keyword_str) > 30:
        keyword_str = keyword_str[:30]

    filename = f"{date_str}_{keyword_str}.bib"
    return base_dir / filename


def _save_output(results: SearchResults, output: Path, format: str, config):
    """Save results to output file."""
    # Ensure parent directory exists
    output.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        output_text = results.to_json()
        output.write_text(output_text)
    else:
        output_text = results.to_bibtex(config.citekey)
        output.write_text(output_text)

    # Serpapi extra: save separately if available
    if results.serpapi_extra and output:
        serpapi_file = output.parent / f"{output.stem}_serpapi.json"
        serpapi_data = {
            "query": results.query,
            "serpapi_extra": [e.to_dict() for e in results.serpapi_extra],
        }
        serpapi_file.write_text(json.dumps(serpapi_data, indent=2))
        console.print(f"[green]Serpapi extra saved to {serpapi_file}[/green]")