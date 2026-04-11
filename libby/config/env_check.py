"""Environment variable status check."""

import os

from rich.console import Console

console = Console()

ENV_VARS = {
    "S2_API_KEY": ("Semantic Scholar API", "100 req/5min with key", "1 req/sec without"),
    "SERPAPI_API_KEY": ("Serpapi", "Google Scholar fallback", "Skip method"),
    "EMAIL": ("Unpaywall", "OA PDF lookup", "Skip method"),
    "DEEPSEEK_API_KEY": ("AI Extractor", "PDF DOI/title extraction", "Skip feature"),
}


def check_env_vars():
    """Check and display environment variable status."""
    for var, (name, benefit, fallback) in ENV_VARS.items():
        value = os.getenv(var)
        if value:
            console.print(f"[green][OK][/green] {var}: {name} enabled ({benefit})")
        else:
            console.print(f"[red][--][/red] {var}: {name} disabled ({fallback})")