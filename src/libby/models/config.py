"""Configuration models using pydantic."""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class CitekeyConfig(BaseModel):
    """Citekey formatting configuration."""

    pattern: str = "{author}_{year}_{title}"
    author_words: int = 1
    title_words: int = 3
    title_chars_per_word: int = 0  # 0 = no limit
    case: str = "lowercase"  # lowercase, camelcase
    ascii_only: bool = True
    ignored_words: list[str] = Field(default_factory=lambda: [
        "the", "a", "an", "of", "for", "in", "at", "to", "and",
        "do", "does", "is", "are", "was", "were", "be", "been",
        "that", "this", "these", "those", "on", "by", "with", "from",
    ])


class RetryConfig(BaseModel):
    """Retry configuration for API calls."""

    max_retries: int = 5
    delays: list[int] = Field(default_factory=lambda: [1, 2, 4, 15, 60])


class SerpapiConfig(BaseModel):
    """Serpapi/BibTeX fetching configuration."""

    # API key (optional, can also use SERPAPI_API_KEY env var)
    api_key: Optional[str] = None
    # Max parallel workers for BibTeX fetching (Selenium)
    max_bibtex_workers: int = 5
    # Upper limit for workers (safety)
    max_workers_limit: int = 20


class SemanticScholarConfig(BaseModel):
    """Semantic Scholar API configuration."""

    # API key (optional, can also use S2_API_KEY env var)
    api_key: Optional[str] = None


class UnpaywallConfig(BaseModel):
    """Unpaywall API configuration."""

    # Email for Unpaywall access (optional, can also use EMAIL env var)
    email: Optional[str] = None


class AIExtractorConfig(BaseModel):
    """AI extractor configuration."""

    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    max_tokens: int = 1000


class LibbyConfig(BaseModel):
    """Main configuration for libby.

    lib_dir: Base directory for all libby data.
    Subdirectories are auto-generated:
        - papers/: PDF files and BibTeX metadata
        - extract_task/: Failed extraction task logs
        - search_results/: Websearch output files
    """

    lib_dir: Path = Field(default_factory=lambda: Path.home() / ".lib")
    citekey: CitekeyConfig = Field(default_factory=CitekeyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    serpapi: SerpapiConfig = Field(default_factory=SerpapiConfig)
    semantic_scholar: SemanticScholarConfig = Field(default_factory=SemanticScholarConfig)
    unpaywall: UnpaywallConfig = Field(default_factory=UnpaywallConfig)
    ai_extractor: AIExtractorConfig = Field(default_factory=AIExtractorConfig)
    config_path: Optional[Path] = None

    # Fetch configuration
    scihub_url: str = "https://sci-hub.ru"
    pdf_max_size: int = 50 * 1024 * 1024  # 50 MB

    model_config = ConfigDict(extra="ignore")

    @property
    def papers_dir(self) -> Path:
        """Papers directory: lib_dir/papers/"""
        return self.lib_dir / "papers"

    @property
    def extract_task_dir(self) -> Path:
        """Extract task logs directory: lib_dir/extract_task/"""
        return self.lib_dir / "extract_task"

    @property
    def search_results_dir(self) -> Path:
        """Search results directory: lib_dir/search_results/"""
        return self.lib_dir / "search_results"

    def get_s2_api_key(self) -> Optional[str]:
        """Get S2 API key from config or environment."""
        return self.semantic_scholar.api_key or os.getenv("S2_API_KEY")

    def get_serpapi_api_key(self) -> Optional[str]:
        """Get Serpapi API key from config or environment."""
        return self.serpapi.api_key or os.getenv("SERPAPI_API_KEY")

    def get_email(self) -> Optional[str]:
        """Get email for Unpaywall from config or environment."""
        return self.unpaywall.email or os.getenv("EMAIL")

    def get_ai_api_key(self) -> Optional[str]:
        """Get AI API key from config or environment."""
        return self.ai_extractor.api_key or os.getenv("DEEPSEEK_API_KEY")