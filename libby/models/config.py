"""Configuration models using pydantic."""

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

    # Max parallel workers for BibTeX fetching (Selenium)
    max_bibtex_workers: int = 5
    # Upper limit for workers (safety)
    max_workers_limit: int = 20


class AIExtractorConfig(BaseModel):
    """AI extractor configuration."""

    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    max_tokens: int = 1000


class LibbyConfig(BaseModel):
    """Main configuration for libby."""

    papers_dir: Path = Field(default_factory=lambda: Path.home() / ".lib" / "papers")
    citekey: CitekeyConfig = Field(default_factory=CitekeyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    serpapi: SerpapiConfig = Field(default_factory=SerpapiConfig)
    ai_extractor: AIExtractorConfig = Field(default_factory=AIExtractorConfig)
    config_path: Optional[Path] = None

    # Fetch configuration
    scihub_url: str = "https://sci-hub.ru"
    pdf_max_size: int = 50 * 1024 * 1024  # 50 MB

    model_config = ConfigDict(extra="ignore")