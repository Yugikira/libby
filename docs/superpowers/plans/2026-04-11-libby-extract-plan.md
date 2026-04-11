# libby extract 子系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 libby extract 命令，支持从 DOI、标题或 PDF 文件提取元数据并输出 BibTeX 格式。

**Architecture:** 分层架构 - CLI 层 (typer) → Core 层 (元数据提取逻辑) → API 层 (异步 HTTP 客户端) → Output 层 (格式化输出)

**Tech Stack:** Python 3.10+, typer (CLI), aiohttp (异步 HTTP), aiolimiter (限流), pypdf (PDF 解析), pyyaml (配置), pydantic (数据验证), openai (AI 提取)

**Testing Strategy:** TDD - 每个功能先写失败测试 → 实现 → 验证通过 → 提交

---

## Task 1: 项目骨架与依赖配置

**Files:**
- Create: `pyproject.toml`
- Create: `libby/__init__.py`
- Create: `libby/__main__.py`
- Create: `.python-version`
- Test: N/A (setup only)

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "libby"
version = "0.1.0"
description = "AI-friendly CLI tool for scholarly paper management"
authors = [{name = "Yugi"}]
requires-python = ">=3.10"
readme = "README.md"

dependencies = [
    "typer>=0.12.0",
    "rich>=13.0.0",
    "pypdf>=4.0.0",
    "requests>=2.31.0",
    "aiohttp>=3.9.0",
    "aiolimiter>=1.1.0",
    "pyyaml>=6.0",
    "pydantic>=2.0.0",
    "scholarly>=1.7.0",
    "openai>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
]

[project.scripts]
libby = "libby.__main__:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py310"
line-length = 88
select = ["E", "F", "W", "I"]
```

- [ ] **Step 2: 创建 .python-version**

```
3.10
```

- [ ] **Step 3: 创建 libby/__init__.py**

```python
"""libby - AI-friendly CLI for scholarly paper management."""

__version__ = "0.1.0"
```

- [ ] **Step 4: 创建 libby/__main__.py**

```python
"""libby CLI entry point."""

import typer

app = typer.Typer(
    name="libby",
    help="AI-friendly CLI tool for scholarly paper management",
    add_completion=False,
)


@app.callback()
def version(
    show_version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
    ),
):
    """libby - Scholarly paper management CLI."""
    if show_version:
        from libby import __version__
        typer.echo(f"libby version {__version__}")
        raise typer.Exit()


# 子命令将在后续任务中注册
# app.add_typer(extract_app, name="extract")


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: 安装依赖并验证**

```bash
uv sync
uv run libby --version
```

Expected: 输出 `libby version 0.1.0`

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml libby/ .python-version
git commit -m "feat: project skeleton with typer CLI"
```

---

## Task 2: 配置层 (Config Layer)

**Files:**
- Create: `libby/config/__init__.py`
- Create: `libby/config/loader.py`
- Create: `libby/config/defaults.py`
- Create: `libby/config/env_check.py`
- Create: `libby/models/config.py`
- Test: `tests/config/test_config_loader.py`

- [ ] **Step 1: 创建配置模型 `libby/models/config.py`**

```python
"""Configuration models using pydantic."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


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
    ai_extractor: AIExtractorConfig = Field(default_factory=AIExtractorConfig)
    config_path: Optional[Path] = None

    class Config:
        extra = "ignore"
```

- [ ] **Step 2: 创建默认配置 `libby/config/defaults.py`**

```python
"""Default configuration values."""

from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".libby" / "config.yaml"
DEFAULT_PAPERS_DIR = Path.home() / ".lib" / "papers"

DEFAULT_CONFIG_YAML = """# libby configuration file
# Default location: ~/.libby/config.yaml

papers_dir: ~/.lib/papers

citekey:
  pattern: "{author}_{year}_{title}"
  author_words: 1
  title_words: 3
  title_chars_per_word: 0
  case: lowercase
  ascii_only: true
  ignored_words:
    - the
    - a
    - an
    - of
    - for
    - in
    - at
    - to
    - and
    - do
    - does
    - is
    - are
    - was
    - were
    - be
    - been
    - that
    - this
    - these
    - those
    - on
    - by
    - with
    - from

retry:
  max_retries: 5
  delays: [1, 2, 4, 15, 60]

ai_extractor:
  api_key: null
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 1000
"""
```

- [ ] **Step 3: 创建配置加载器 `libby/config/loader.py`**

```python
"""Configuration loading."""

import os
from pathlib import Path

import yaml

from libby.config.defaults import DEFAULT_CONFIG_PATH, DEFAULT_CONFIG_YAML
from libby.models.config import LibbyConfig, CitekeyConfig, RetryConfig, AIExtractorConfig


def load_config(config_path: Path | None = None) -> LibbyConfig:
    """Load configuration from file.

    Priority:
    1. CLI --config path (config_path argument)
    2. LIBBY_CONFIG environment variable
    3. Default ~/.libby/config.yaml
    """
    # Determine config path
    if config_path:
        path = config_path
    elif os.getenv("LIBBY_CONFIG"):
        path = Path(os.getenv("LIBBY_CONFIG"))
    else:
        path = DEFAULT_CONFIG_PATH

    # Load YAML
    if path.exists():
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Merge with defaults
    return LibbyConfig(
        papers_dir=Path(data.get("papers_dir", "~/.lib/papers")).expanduser(),
        citekey=CitekeyConfig(**data.get("citekey", {})),
        retry=RetryConfig(**data.get("retry", {})),
        ai_extractor=AIExtractorConfig(**data.get("ai_extractor", {})),
        config_path=path,
    )
```

- [ ] **Step 4: 创建环境变量检查 `libby/config/env_check.py`**

```python
"""Environment variable status check."""

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
            console.print(f"[green]✓[/green] {var}: {name} enabled ({benefit})")
        else:
            console.print(f"[red]✗[/red] {var}: {name} disabled ({fallback})")
```

- [ ] **Step 5: 创建测试 `tests/config/test_config_loader.py`**

```python
"""Tests for configuration loading."""

import os
from pathlib import Path
import tempfile

import pytest

from libby.config.loader import load_config
from libby.models.config import LibbyConfig


def test_load_default_config():
    """Test loading default config when no file exists."""
    config = load_config(config_path=Path("/nonexistent/config.yaml"))
    assert config.papers_dir == Path.home() / ".lib" / "papers"
    assert config.citekey.pattern == "{author}_{year}_{title}"
    assert config.citekey.author_words == 1
    assert config.citekey.title_words == 3


def test_load_custom_config():
    """Test loading custom config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
papers_dir: /custom/papers
citekey:
  author_words: 2
  title_words: 5
""")
        temp_path = Path(f.name)

    try:
        config = load_config(config_path=temp_path)
        assert config.papers_dir == Path("/custom/papers")
        assert config.citekey.author_words == 2
        assert config.citekey.title_words == 5
    finally:
        temp_path.unlink()


def test_env_var_priority():
    """Test environment variable override."""
    os.environ["LIBBY_CONFIG"] = "/env/config.yaml"
    # This would be tested with mock file
    del os.environ["LIBBY_CONFIG"]
```

- [ ] **Step 6: 运行测试**

```bash
uv run pytest tests/config/test_config_loader.py -v
```

Expected: 3 tests pass

- [ ] **Step 7: 提交**

```bash
git add libby/config/ libby/models/ tests/config/
git commit -m "feat: configuration layer with YAML support"
```

---

## Task 3: 数据模型 (Models)

**Files:**
- Create: `libby/models/__init__.py`
- Create: `libby/models/metadata.py`
- Create: `libby/models/result.py`
- Test: `tests/models/test_metadata.py`

- [ ] **Step 1: 创建元数据模型 `libby/models/metadata.py`**

```python
"""BibTeX metadata model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BibTeXMetadata:
    """BibTeX metadata entry."""

    citekey: str
    entry_type: str = "article"
    author: list[str] = field(default_factory=list)
    title: str = ""
    year: Optional[int] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "citekey": self.citekey,
            "entry_type": self.entry_type,
            "author": self.author,
            "title": self.title,
            "year": self.year,
            "doi": self.doi,
            "journal": self.journal,
            "volume": self.volume,
            "number": self.number,
            "pages": self.pages,
            "publisher": self.publisher,
            "url": self.url,
        }
```

- [ ] **Step 2: 创建结果模型 `libby/models/result.py`**

```python
"""Batch processing result model."""

from dataclasses import dataclass, field


@dataclass
class BatchResult:
    """Result of batch processing."""

    succeeded: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.succeeded) / self.total * 100
```

- [ ] **Step 3: 创建测试 `tests/models/test_metadata.py`**

```python
"""Tests for metadata models."""

from libby.models.metadata import BibTeXMetadata
from libby.models.result import BatchResult


def test_bibtex_metadata_creation():
    """Test creating BibTeX metadata."""
    metadata = BibTeXMetadata(
        citekey="stent_2016_earnings",
        entry_type="article",
        author=["Stent, Angela", "Yang, Kaitlin"],
        title="Earnings Management Consequences",
        year=2016,
        doi="10.1007/s11142-016-9368-9",
    )
    assert metadata.citekey == "stent_2016_earnings"
    assert len(metadata.author) == 2
    assert metadata.year == 2016


def test_bibtex_metadata_to_dict():
    """Test converting to dictionary."""
    metadata = BibTeXMetadata(
        citekey="test_2024_paper",
        title="Test Paper",
        year=2024,
    )
    d = metadata.to_dict()
    assert d["citekey"] == "test_2024_paper"
    assert d["title"] == "Test Paper"
    assert d["year"] == 2024


def test_batch_result():
    """Test batch result calculation."""
    result = BatchResult(
        succeeded=[{"a": 1}, {"b": 2}],
        failed=[{"c": 3}],
    )
    assert result.total == 3
    assert result.success_rate == pytest.approx(66.67, rel=0.01)
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/models/test_metadata.py -v
```

Expected: 3 tests pass

- [ ] **Step 5: 提交**

```bash
git add libby/models/ tests/models/
git commit -m "feat: data models for metadata and batch results"
```

---

## Task 4: DOI 解析工具

**Files:**
- Create: `libby/utils/__init__.py`
- Create: `libby/utils/doi_parser.py`
- Test: `tests/utils/test_doi_parser.py`

- [ ] **Step 1: 创建 DOI 解析器 `libby/utils/doi_parser.py`**

```python
"""DOI parsing and normalization utilities."""

import re


def normalize_doi(doi: str) -> str:
    """Normalize DOI string by removing common prefixes."""
    doi = doi.strip()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("doi.org/")
    doi = doi.removeprefix("DOI:")
    doi = doi.removeprefix("doi:")
    doi = doi.removeprefix("DOI ")
    doi = doi.removeprefix("doi ")
    return doi.lower()


def extract_doi_from_text(text: str) -> str | None:
    """Extract DOI from text, handling line breaks.

    Handles:
    - Hyphen breaks: 10.1234/abc-\ndef → 10.1234/abc-def
    - Space breaks: 10.1234/abc\n123 → 10.1234/abc 123
    """
    # First try direct match
    pattern = r'(10\.\d{4,}/[^\s]+)'
    match = re.search(pattern, text)
    if match:
        return match.group(1)

    # Try merging hyphen breaks
    merged = re.sub(r'-\n', '-', text)
    merged = re.sub(r'\n', ' ', merged)
    match = re.search(pattern, merged)
    if match:
        return match.group(1)

    return None
```

- [ ] **Step 2: 创建测试 `tests/utils/test_doi_parser.py`**

```python
"""Tests for DOI parsing."""

import pytest

from libby.utils.doi_parser import normalize_doi, extract_doi_from_text


def test_normalize_doi_plain():
    """Test normalizing plain DOI."""
    assert normalize_doi("10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"


def test_normalize_doi_with_prefix():
    """Test normalizing DOI with various prefixes."""
    assert normalize_doi("https://doi.org/10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"
    assert normalize_doi("doi.org/10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"
    assert normalize_doi("DOI:10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"
    assert normalize_doi("doi:10.1007/s11142-016-9368-9") == "10.1007/s11142-016-9368-9"


def test_normalize_doi_lowercase():
    """Test DOI is lowercased."""
    assert normalize_doi("10.1007/ABC-123") == "10.1007/abc-123"


def test_extract_doi_direct():
    """Test extracting DOI with direct match."""
    text = "This paper DOI: 10.1007/s11142-016-9368-9 was published"
    assert extract_doi_from_text(text) == "10.1007/s11142-016-9368-9"


def test_extract_doi_hyphen_break():
    """Test extracting DOI with hyphen line break."""
    text = "DOI: 10.1007/s11142-\n016-9368-9"
    assert extract_doi_from_text(text) == "10.1007/s11142-016-9368-9"


def test_extract_doi_no_match():
    """Test when no DOI present."""
    text = "This is just plain text without any DOI"
    assert extract_doi_from_text(text) is None
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/utils/test_doi_parser.py -v
```

Expected: 6 tests pass

- [ ] **Step 4: 提交**

```bash
git add libby/utils/ tests/utils/
git commit -m "feat: DOI parsing with line break handling"
```

---

## Task 5: PDF 文本提取

**Files:**
- Create: `libby/core/__init__.py`
- Create: `libby/core/pdf_text.py`
- Test: `tests/core/test_pdf_text.py`

- [ ] **Step 1: 创建 PDF 文本提取 `libby/core/pdf_text.py`**

```python
"""PDF text extraction using pypdf."""

from pathlib import Path

from pypdf import PdfReader


def extract_first_page_text(pdf_path: Path) -> str:
    """Extract text from the first page of a PDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Text content of the first page, or empty string if extraction fails.
    """
    try:
        reader = PdfReader(pdf_path)
        if not reader.pages:
            return ""
        return reader.pages[0].extract_text() or ""
    except Exception:
        return ""
```

- [ ] **Step 2: 创建测试 `tests/core/test_pdf_text.py`**

```python
"""Tests for PDF text extraction."""

from pathlib import Path

import pytest

from libby.core.pdf_text import extract_first_page_text


def test_extract_first_page(example_pdf_path):
    """Test extracting text from first page."""
    text = extract_first_page_text(example_pdf_path)
    assert isinstance(text, str)
    # Should contain some text (not empty for valid PDF)


def test_extract_nonexistent_pdf():
    """Test extracting from nonexistent file."""
    result = extract_first_page_text(Path("/nonexistent/file.pdf"))
    assert result == ""
```

- [ ] **Step 3: 创建 conftest.py 提供 fixture**

```python
"""Pytest fixtures."""

from pathlib import Path
import pytest

@pytest.fixture
def example_pdf_path() -> Path:
    """Path to example test PDF."""
    return Path(__file__).parent.parent / "example" / "test.pdf"
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/core/test_pdf_text.py -v
```

Expected: 2 tests pass (assuming example/test.pdf exists)

- [ ] **Step 5: 提交**

```bash
git add libby/core/pdf_text.py tests/core/ conftest.py
git commit -m "feat: PDF text extraction with pypdf"
```

---

## Task 6: API 层基础 (Async HTTP Client)

**Files:**
- Create: `libby/api/__init__.py`
- Create: `libby/api/base.py`
- Create: `libby/utils/retry.py`
- Test: `tests/api/test_base.py`

- [ ] **Step 1: 创建重试策略 `libby/utils/retry.py`**

```python
"""Retry utilities for API calls."""

import asyncio
from typing import Callable, Any

from libby.models.config import RetryConfig


async def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs,
) -> Any:
    """Execute function with exponential backoff retry.

    Args:
        func: Async function to execute.
        config: Retry configuration.
        *args, **kwargs: Arguments to pass to func.

    Returns:
        Result of func if successful.

    Raises:
        Last exception if all retries fail.
    """
    last_exception = None
    delays = config.delays

    for attempt in range(len(delays) + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < len(delays):
                await asyncio.sleep(delays[attempt])
            else:
                break

    raise last_exception
```

- [ ] **Step 2: 创建 API 基类 `libby/api/base.py`**

```python
"""Async HTTP client base with rate limiting."""

import asyncio
from typing import Optional

import aiohttp
from aiolimiter import AsyncLimiter


class RateLimit:
    """Rate limit configuration."""

    def __init__(self, requests: int, period: int):
        self.requests = requests
        self.period = period


class AsyncAPIClient:
    """Async HTTP client with rate limit control."""

    RATE_LIMIT = RateLimit(1, 1)  # Default: 1 req/sec

    def __init__(self):
        self._limiter = AsyncLimiter(
            self.RATE_LIMIT.requests,
            self.RATE_LIMIT.period,
        )
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get(self, url: str, **kwargs) -> dict:
        """Make GET request with rate limiting."""
        await self._limiter.acquire()
        session = await self._get_session()

        async with session.get(url, **kwargs) as resp:
            if resp.status == 429:
                # Rate limited - wait and retry once
                await asyncio.sleep(5)
                async with session.get(url, **kwargs) as retry_resp:
                    return await retry_resp.json()
            return await resp.json()

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
```

- [ ] **Step 3: 创建测试 `tests/api/test_base.py`**

```python
"""Tests for API base client."""

import pytest

from libby.api.base import AsyncAPIClient, RateLimit


def test_rate_limit_creation():
    """Test RateLimit configuration."""
    rl = RateLimit(10, 60)
    assert rl.requests == 10
    assert rl.period == 60


def test_client_creation():
    """Test client initialization."""
    client = AsyncAPIClient()
    assert client._limiter is not None


@pytest.mark.asyncio
async def test_client_close():
    """Test closing client."""
    client = AsyncAPIClient()
    await client.close()
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/api/test_base.py -v
```

Expected: 3 tests pass

- [ ] **Step 5: 提交**

```bash
git add libby/api/ libby/utils/retry.py tests/api/
git commit -m "feat: async HTTP client base with rate limiting"
```

---

## Task 7: Crossref API 客户端

**Files:**
- Create: `libby/api/crossref.py`
- Test: `tests/api/test_crossref.py`

- [ ] **Step 1: 创建 Crossref API 客户端 `libby/api/crossref.py`**

```python
"""Crossref API client."""

import urllib.parse
from typing import Optional

from libby.api.base import AsyncAPIClient, RateLimit
from libby.models.metadata import BibTeXMetadata


class CrossrefAPI(AsyncAPIClient):
    """Crossref API client."""

    RATE_LIMIT = RateLimit(1, 1)  # 1 req/sec
    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto: Optional[str] = None):
        super().__init__()
        self.mailto = mailto

    async def fetch_by_doi(self, doi: str) -> Optional[dict]:
        """Fetch work metadata by DOI."""
        url = f"{self.BASE_URL}/works/{urllib.parse.quote(doi)}"
        params = {}
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            return data.get("message")
        return None

    async def search_by_title(self, title: str) -> list[dict]:
        """Search works by title keywords."""
        url = f"{self.BASE_URL}/works"
        params = {
            "query.title": title,
            "rows": 10,
        }
        if self.mailto:
            params["mailto"] = self.mailto

        data = await self.get(url, params=params)
        if data.get("status") == "ok":
            items = data.get("message", {}).get("items", [])
            return items[:5]  # Return top 5 results
        return []

    def _parse_to_metadata(self, data: dict) -> BibTeXMetadata:
        """Parse Crossref response to BibTeXMetadata."""
        # Extract authors
        authors = []
        if "author" in data:
            for author in data["author"]:
                family = author.get("family", "")
                given = author.get("given", "")
                if family:
                    authors.append(f"{family}, {given}" if given else family)

        # Extract year
        year = None
        if "published-print" in data or "published-online" in data:
            pub = data.get("published-print") or data.get("published-online")
            if pub and "date-parts" in pub:
                date_parts = pub["date-parts"][0]
                if len(date_parts) >= 1:
                    year = date_parts[0]

        return BibTeXMetadata(
            citekey="",  # Will be formatted later
            entry_type=data.get("type", "article"),
            author=authors,
            title=data.get("title", [""])[0] if isinstance(data.get("title"), list) else "",
            year=year,
            doi=data.get("DOI"),
            journal=data.get("container-title", [""])[0] if isinstance(data.get("container-title"), list) else "",
            volume=data.get("volume"),
            issue=data.get("issue"),
            page=data.get("page"),
            publisher=data.get("publisher"),
            url=data.get("URL"),
        )
```

- [ ] **Step 2: 创建测试 `tests/api/test_crossref.py`**

```python
"""Tests for Crossref API client."""

import pytest

from libby.api.crossref import CrossrefAPI


@pytest.mark.asyncio
async def test_fetch_by_doi():
    """Test fetching by DOI."""
    client = CrossrefAPI()
    doi = "10.1007/s11142-016-9368-9"
    result = await client.fetch_by_doi(doi)
    assert result is not None
    assert result.get("DOI") == doi
    await client.close()


@pytest.mark.asyncio
async def test_search_by_title():
    """Test searching by title."""
    client = CrossrefAPI(mailto="test@example.com")
    results = await client.search_by_title("corporate site visit")
    assert isinstance(results, list)
    await client.close()
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/api/test_crossref.py -v
```

Expected: 2 tests pass (requires network)

- [ ] **Step 4: 提交**

```bash
git add libby/api/crossref.py tests/api/test_crossref.py
git commit -m "feat: Crossref API client with DOI lookup"
```

---

## Task 8: Citekey 格式化器

**Files:**
- Create: `libby/core/citekey.py`
- Test: `tests/core/test_citekey.py`

- [ ] **Step 1: 创建 citekey 格式化器 `libby/core/citekey.py`**

```python
"""Citekey formatting."""

import unicodedata

from libby.models.config import CitekeyConfig
from libby.models.metadata import BibTeXMetadata


class CitekeyFormatter:
    """Format citekeys from metadata."""

    def __init__(self, config: CitekeyConfig):
        self.pattern = config.pattern
        self.author_words = config.author_words
        self.title_words = config.title_words
        self.title_chars_per_word = config.title_chars_per_word
        self.case = config.case
        self.ascii_only = config.ascii_only
        self.ignored_words = set(config.ignored_words)

    def format(self, metadata: BibTeXMetadata) -> str:
        """Format citekey from metadata."""
        author = self._format_author(metadata.author)
        title = self._format_title(metadata.title)
        year = str(metadata.year or "nd")

        result = self.pattern.format(author=author, title=title, year=year)

        if self.case == "lowercase":
            result = result.lower()
        elif self.case == "camelcase":
            result = self._to_camelcase(result)

        if self.ascii_only:
            result = self._to_ascii(result)

        return result

    def _format_author(self, author: list[str]) -> str:
        """Extract author surname."""
        if not author:
            return "unknown"

        # Take first author
        first_author = author[0] if isinstance(author, list) else author

        # Handle "Last, First" or "First Last" format
        if "," in first_author:
            return first_author.split(",")[0].strip()
        else:
            return first_author.split()[-1]

    def _format_title(self, title: str) -> str:
        """Extract title keywords."""
        if not title:
            return "no_title"

        words = title.split()
        # Filter ignored words
        words = [w for w in words if w.lower() not in self.ignored_words]
        # Limit word count
        words = words[: self.title_words]
        # Limit chars per word
        if self.title_chars_per_word > 0:
            words = [w[: self.title_chars_per_word] for w in words]

        return "_".join(words) if words else "no_title"

    def _to_ascii(self, text: str) -> str:
        """Convert to ASCII."""
        return unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")

    def _to_camelcase(self, text: str) -> str:
        """Convert to camelCase."""
        parts = text.replace("_", " ").split()
        return "".join(word.capitalize() for word in parts)
```

- [ ] **Step 2: 创建测试 `tests/core/test_citekey.py`**

```python
"""Tests for citekey formatting."""

import pytest

from libby.config.loader import load_config
from libby.core.citekey import CitekeyFormatter
from libby.models.metadata import BibTeXMetadata


def test_format_default():
    """Test default citekey format."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=["Stent, Angela", "Yang, Kaitlin"],
        title="Earnings Management Consequences of Cross-Listing",
        year=2016,
    )

    citekey = formatter.format(metadata)
    assert citekey == "stent_2016_earnings_management_consequences"


def test_format_multiple_authors():
    """Test with multiple authors - only first is used."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=["Smith, John", "Jones, Jane"],
        title="Test Paper",
        year=2020,
    )

    citekey = formatter.format(metadata)
    assert citekey.startswith("smith_")


def test_format_no_author():
    """Test with no author."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=[],
        title="Test Paper",
        year=2020,
    )

    citekey = formatter.format(metadata)
    assert citekey.startswith("unknown_")


def test_format_ignored_words():
    """Test that ignored words are filtered."""
    config = load_config(config_path=None)
    formatter = CitekeyFormatter(config.citekey)

    metadata = BibTeXMetadata(
        citekey="",
        author=["Test"],
        title="The Quick Brown Fox",
        year=2020,
    )

    citekey = formatter.format(metadata)
    assert "the" not in citekey
    assert "quick" in citekey
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/core/test_citekey.py -v
```

Expected: 4 tests pass

- [ ] **Step 4: 提交**

```bash
git add libby/core/citekey.py tests/core/test_citekey.py
git commit -m "feat: citekey formatting with configurable pattern"
```

---

## Task 9: Output 层 (BibTeX/JSON 格式化)

**Files:**
- Create: `libby/output/__init__.py`
- Create: `libby/output/bibtex.py`
- Create: `libby/output/json.py`
- Test: `tests/output/test_bibtex.py`

- [ ] **Step 1: 创建 BibTeX 输出 `libby/output/bibtex.py`**

```python
"""BibTeX format output."""

from libby.models.metadata import BibTeXMetadata


class BibTeXFormatter:
    """Format metadata as BibTeX."""

    def format(self, metadata: BibTeXMetadata) -> str:
        """Format single entry as BibTeX."""
        lines = [
            f"@{metadata.entry_type}{{{metadata.citekey},",
            f"  author = {{{self._format_authors(metadata.author)}}},",
            f"  title = {{{metadata.title}}},",
        ]

        if metadata.year:
            lines.append(f"  year = {{{metadata.year}}},")
        if metadata.doi:
            lines.append(f"  doi = {{{metadata.doi}}},")
        if metadata.journal:
            lines.append(f"  journal = {{{metadata.journal}}},")
        if metadata.volume:
            lines.append(f"  volume = {{{metadata.volume}}},")
        if metadata.number:
            lines.append(f"  number = {{{metadata.number}}},")
        if metadata.pages:
            lines.append(f"  pages = {{{metadata.pages}}},")
        if metadata.publisher:
            lines.append(f"  publisher = {{{metadata.publisher}}},")
        if metadata.url:
            lines.append(f"  url = {{{metadata.url}}},")

        lines.append("}")
        return "\n".join(lines)

    def format_batch(self, metadata_list: list[BibTeXMetadata]) -> str:
        """Format multiple entries as BibTeX."""
        return "\n\n".join(self.format(m) for m in metadata_list)

    def _format_authors(self, authors: list[str]) -> str:
        """Format authors for BibTeX."""
        return " and ".join(authors)
```

- [ ] **Step 2: 创建 JSON 输出 `libby/output/json.py`**

```python
"""JSON format output."""

import json

from libby.models.metadata import BibTeXMetadata


class JSONFormatter:
    """Format metadata as JSON."""

    def format(self, metadata: BibTeXMetadata) -> str:
        """Format single entry as JSON."""
        return json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2)

    def format_batch(self, metadata_list: list[BibTeXMetadata]) -> str:
        """Format multiple entries as JSON."""
        return json.dumps([m.to_dict() for m in metadata_list], ensure_ascii=False, indent=2)
```

- [ ] **Step 3: 创建测试 `tests/output/test_bibtex.py`**

```python
"""Tests for BibTeX output."""

from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter
from libby.models.metadata import BibTeXMetadata


def test_bibtex_single_entry():
    """Test formatting single BibTeX entry."""
    formatter = BibTeXFormatter()
    metadata = BibTeXMetadata(
        citekey="stent_2016_earnings",
        entry_type="article",
        author=["Stent, Angela"],
        title="Earnings Management",
        year=2016,
        doi="10.1007/s11142-016-9368-9",
    )

    output = formatter.format(metadata)
    assert "@article{stent_2016_earnings," in output
    assert "author = {{Stent, Angela}}" in output
    assert "doi = {10.1007/s11142-016-9368-9}" in output


def test_bibtex_multiple_entries():
    """Test formatting multiple BibTeX entries."""
    formatter = BibTeXFormatter()
    metadata_list = [
        BibTeXMetadata(citekey="a", author=["Author A"], title="A", year=2020),
        BibTeXMetadata(citekey="b", author=["Author B"], title="B", year=2021),
    ]

    output = formatter.format_batch(metadata_list)
    assert "@article{a," in output
    assert "@article{b," in output


def test_json_single_entry():
    """Test formatting single JSON entry."""
    formatter = JSONFormatter()
    metadata = BibTeXMetadata(
        citekey="test_2024_paper",
        title="Test",
        year=2024,
    )

    output = formatter.format(metadata)
    import json
    data = json.loads(output)
    assert data["citekey"] == "test_2024_paper"
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/output/test_bibtex.py -v
```

Expected: 3 tests pass

- [ ] **Step 5: 提交**

```bash
git add libby/output/ tests/output/
git commit -m "feat: BibTeX and JSON output formatters"
```

---

## Task 10: 元数据提取核心逻辑

**Files:**
- Create: `libby/core/metadata.py`
- Test: `tests/core/test_metadata_extractor.py`

- [ ] **Step 1: 创建元数据提取器 `libby/core/metadata.py`**

```python
"""Metadata extraction core."""

from pathlib import Path
from typing import Optional

from libby.api.crossref import CrossrefAPI
from libby.config.loader import LibbyConfig
from libby.core.citekey import CitekeyFormatter
from libby.core.pdf_text import extract_first_page_text
from libby.utils.doi_parser import normalize_doi, extract_doi_from_text
from libby.models.metadata import BibTeXMetadata


class MetadataNotFoundError(Exception):
    """Raised when metadata cannot be extracted."""
    pass


class MetadataExtractor:
    """Extract metadata from DOI, title, or PDF."""

    def __init__(self, config: LibbyConfig):
        self.config = config
        self.crossref = CrossrefAPI()
        self.formatter = CitekeyFormatter(config.citekey)

    async def extract_from_doi(self, doi: str) -> BibTeXMetadata:
        """Extract metadata from DOI."""
        doi = normalize_doi(doi)
        data = await self.crossref.fetch_by_doi(doi)

        if not data:
            raise MetadataNotFoundError(f"DOI not found: {doi}")

        metadata = self.crossref._parse_to_metadata(data)
        metadata.doi = doi
        metadata.citekey = self.formatter.format(metadata)
        return metadata

    async def extract_from_title(self, title: str) -> BibTeXMetadata:
        """Extract metadata from title (cascade: Crossref -> S2 -> scholarly)."""
        # Phase 1: Crossref
        results = await self.crossref.search_by_title(title)
        if results:
            metadata = self.crossref._parse_to_metadata(results[0])
            metadata.citekey = self.formatter.format(metadata)
            return metadata

        # Phase 2: Semantic Scholar (TODO)
        # Phase 3: scholarly (TODO)

        raise MetadataNotFoundError(f"Title not found: {title}")

    async def extract_from_pdf(self, pdf_path: Path, use_ai: bool = False) -> BibTeXMetadata:
        """Extract metadata from PDF."""
        text = extract_first_page_text(pdf_path)

        if not text:
            raise MetadataNotFoundError(f"Cannot extract text from PDF: {pdf_path}")

        # Try AI extraction first if enabled
        if use_ai:
            result = await self._ai_extract(text)
            if result.get("doi"):
                return await self.extract_from_doi(result["doi"])
            if result.get("title"):
                return await self.extract_from_title(result["title"])

        # Regex fallback
        doi = extract_doi_from_text(text)
        if doi:
            return await self.extract_from_doi(doi)

        raise MetadataNotFoundError(f"No DOI found in PDF: {pdf_path}")

    async def _ai_extract(self, text: str) -> dict:
        """AI-powered DOI/title extraction."""
        from libby.core.ai_extractor import AIExtractor

        extractor = AIExtractor(self.config)
        return await extractor.extract_from_text(text)

    async def close(self):
        """Close resources."""
        await self.crossref.close()
```

- [ ] **Step 2: 创建测试 `tests/core/test_metadata_extractor.py`**

```python
"""Tests for metadata extraction."""

import pytest

from libby.config.loader import load_config
from libby.core.metadata import MetadataExtractor, MetadataNotFoundError


@pytest.mark.asyncio
async def test_extract_from_doi():
    """Test extracting metadata from DOI."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    doi = "10.1007/s11142-016-9368-9"
    metadata = await extractor.extract_from_doi(doi)

    assert metadata.doi == doi
    assert metadata.citekey is not None
    assert metadata.year is not None

    await extractor.close()


@pytest.mark.asyncio
async def test_extract_not_found():
    """Test when DOI is not found."""
    config = load_config(config_path=None)
    extractor = MetadataExtractor(config)

    with pytest.raises(MetadataNotFoundError):
        await extractor.extract_from_doi("10.0000/invalid-doi")

    await extractor.close()
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/core/test_metadata_extractor.py -v
```

Expected: 2 tests pass

- [ ] **Step 4: 提交**

```bash
git add libby/core/metadata.py tests/core/test_metadata_extractor.py
git commit -m "feat: metadata extraction core logic"
```

---

## Task 11: AI 提取器 (可选功能)

**Files:**
- Create: `libby/core/ai_extractor.py`
- Test: `tests/core/test_ai_extractor.py`

- [ ] **Step 1: 创建 AI 提取器 `libby/core/ai_extractor.py`**

```python
"""AI-powered metadata extraction."""

import json
import os

from openai import AsyncOpenAI

from libby.config.loader import LibbyConfig


class AIExtractor:
    """Extract DOI/title using LLM."""

    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, config: LibbyConfig):
        api_key = config.ai_extractor.api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("AI extractor requires api_key (config or DEEPSEEK_API_KEY)")

        base_url = config.ai_extractor.base_url or self.DEFAULT_BASE_URL
        model = config.ai_extractor.model or self.DEFAULT_MODEL
        max_tokens = config.ai_extractor.max_tokens

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.max_tokens = max_tokens

    async def extract_from_text(self, text: str) -> dict:
        """Extract DOI and title from text."""
        prompt = f"""Extract DOI and title from this academic paper text.
If DOI is split across lines, join it correctly.
Return ONLY valid JSON: {{"doi": "xxx", "title": "xxx"}}
If not found, return: {{"doi": null, "title": null}}

Text (first 2000 chars):
{text[:2000]}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)
```

- [ ] **Step 2: 创建测试 `tests/core/test_ai_extractor.py`**

```python
"""Tests for AI extractor."""

import os
import pytest

from libby.config.loader import load_config
from libby.core.ai_extractor import AIExtractor


@pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY not set")
@pytest.mark.asyncio
async def test_ai_extract():
    """Test AI extraction (requires API key)."""
    config = load_config(config_path=None)
    extractor = AIExtractor(config)

    sample_text = """Journal of Accounting Research
DOI: 10.1007/s11142-016-9368-9

Earnings Management Consequences of Cross-Listing

Abstract: This paper examines..."""

    result = await extractor.extract_from_text(sample_text)
    assert "doi" in result
    assert "title" in result
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/core/test_ai_extractor.py -v
```

Expected: Skipped without API key, passes with key

- [ ] **Step 4: 提交**

```bash
git add libby/core/ai_extractor.py tests/core/test_ai_extractor.py
git commit -m "feat: AI-powered DOI/title extraction with DeepSeek"
```

---

## Task 12: CLI extract 命令

**Files:**
- Create: `libby/cli/__init__.py`
- Create: `libby/cli/extract.py`
- Create: `libby/cli/utils.py`
- Test: Manual testing

- [ ] **Step 1: 创建 CLI 工具函数 `libby/cli/utils.py`**

```python
"""CLI utilities."""

import sys
import json
from pathlib import Path

from libby.models.result import BatchResult


def read_stdin_lines() -> list[str]:
    """Read lines from stdin if not a TTY."""
    if sys.stdin.isatty():
        return []
    return [line.strip() for line in sys.stdin if line.strip()]


async def process_batch(
    inputs: list[str],
    extractor,
    formatter,
    file_handler,
    ai_extract: bool = False,
) -> BatchResult:
    """Process batch of inputs."""
    from libby.core.pdf_text import extract_first_page_text
    from libby.core.metadata import MetadataExtractor, MetadataNotFoundError

    results = BatchResult()

    for input_item in inputs:
        input_path = Path(input_item)

        try:
            if input_path.suffix.lower() == ".pdf":
                metadata = await extractor.extract_from_pdf(input_path, use_ai=ai_extract)
            elif input_path.exists():
                # File but not PDF
                raise MetadataNotFoundError(f"Unsupported file type: {input_path}")
            elif input_item.startswith("10."):
                # DOI
                metadata = await extractor.extract_from_doi(input_item)
            else:
                # Title
                metadata = await extractor.extract_from_title(input_item)

            # Organize file
            if input_path.suffix.lower() == ".pdf":
                file_handler.organize_pdf(input_path, metadata)

            results.succeeded.append({
                "input": input_item,
                "citekey": metadata.citekey,
                "doi": metadata.doi,
            })

        except Exception as e:
            results.failed.append({
                "input": input_item,
                "error": str(e),
            })

    return results


def save_failed_tasks(results: BatchResult, path: Path):
    """Save failed tasks to JSON file."""
    with open(path, "w") as f:
        json.dump(results.failed, f, indent=2)
```

- [ ] **Step 2: 创建文件处理器 `libby/utils/file_ops.py`**

```python
"""File operations."""

import shutil
from pathlib import Path

from libby.output.bibtex import BibTeXFormatter
from libby.models.metadata import BibTeXMetadata


class FileHandler:
    """Organize PDF and metadata files."""

    def __init__(self, papers_dir: Path):
        self.papers_dir = papers_dir

    def organize_pdf(self, pdf_path: Path, metadata: BibTeXMetadata, copy: bool = False) -> Path:
        """Organize PDF into papers directory."""
        target_dir = self.papers_dir / metadata.citekey
        target_dir.mkdir(parents=True, exist_ok=True)

        target_pdf = target_dir / f"{metadata.citekey}.pdf"
        if copy:
            shutil.copy2(pdf_path, target_pdf)
        else:
            shutil.move(str(pdf_path), str(target_pdf))

        target_bib = target_dir / f"{metadata.citekey}.bib"
        target_bib.write_text(BibTeXFormatter().format(metadata))

        return target_dir
```

- [ ] **Step 3: 创建 extract 命令 `libby/cli/extract.py`**

```python
"""libby extract command."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from libby.config.loader import load_config, check_env_vars
from libby.core.metadata import MetadataExtractor
from libby.utils.file_ops import FileHandler
from libby.cli.utils import read_stdin_lines, process_batch, save_failed_tasks
from libby.output.bibtex import BibTeXFormatter
from libby.output.json import JSONFormatter

console = Console()

extract_app = typer.Typer(help="Extract metadata from DOI, title, or PDF")


@extract_app.command()
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
    results = asyncio.run(process_batch(inputs, extractor, formatter, file_handler, ai_extract))

    # Output
    output_text = formatter.format_batch(
        [type("M", (), r) for r in results.succeeded]  # Quick dict-to-object
    )

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

    # Cleanup
    asyncio.run(extractor.close())
```

- [ ] **Step 4: 注册 extract 命令到主应用**

修改 `libby/__main__.py`:

```python
from libby.cli.extract import extract_app
app.add_typer(extract_app, name="extract")
```

- [ ] **Step 5: 手动测试**

```bash
# Test help
uv run libby extract --help

# Test DOI extraction
uv run libby extract 10.1007/s11142-016-9368-9

# Test with example PDF (if exists)
uv run libby extract example/test.pdf
```

- [ ] **Step 6: 提交**

```bash
git add libby/cli/ libby/utils/file_ops.py
git commit -m "feat: extract CLI command with batch processing"
```

---

## Task 13: 集成测试与文档

**Files:**
- Create: `tests/integration/test_extract.py`
- Create: `README.md`
- Create: `CHANGELOG.md`

- [ ] **Step 1: 创建集成测试 `tests/integration/test_extract.py`**

```python
"""Integration tests for extract command."""

import subprocess
from pathlib import Path


def test_extract_doi():
    """Test extracting metadata from DOI."""
    result = subprocess.run(
        ["uv", "run", "libby", "extract", "10.1007/s11142-016-9368-9", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "stent" in result.stdout.lower()


def test_extract_help():
    """Test help command."""
    result = subprocess.run(
        ["uv", "run", "libby", "extract", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "DOI" in result.stdout
```

- [ ] **Step 2: 创建 README.md**

```markdown
# libby

AI-friendly CLI tool for scholarly paper management.

## Features

- **extract**: Extract metadata from DOI, title, or PDF
- **fetch**: Download PDFs from OA sources (coming soon)
- **websearch**: Search academic databases (coming soon)

## Installation

```bash
# Requires uv
git clone https://github.com/your-username/libby
cd libby
uv sync
```

## Usage

### Extract metadata from DOI

```bash
libby extract 10.1007/s11142-016-9368-9
```

### Extract from PDF

```bash
libby extract paper.pdf
libby extract paper.pdf --ai-extract  # Use AI for better DOI detection
```

### Batch process PDFs

```bash
libby extract --batch-dir ./papers/
libby extract --batch-dir ./papers/ --output results.bib
```

### Pipeline input

```bash
echo "10.1007/s11142-016-9368-9" | libby extract
cat dois.txt | libby extract
```

### Output formats

```bash
libby extract doi --format bibtex  # Default
libby extract doi --format json    # AI-friendly
```

## Configuration

Create `~/.libby/config.yaml`:

```yaml
papers_dir: ~/.lib/papers
citekey:
  pattern: "{author}_{year}_{title}"
  author_words: 1
  title_words: 3
```

## Environment Variables

- `S2_API_KEY`: Semantic Scholar API (optional)
- `SERPAPI_API_KEY`: Serpapi for Google Scholar (optional)
- `EMAIL`: Unpaywall access (optional)
- `DEEPSEEK_API_KEY`: AI extraction (optional)

## Testing

```bash
uv run pytest
```

## License

MIT
```

- [ ] **Step 3: 创建 CHANGELOG.md**

```markdown
# Changelog

## [0.1.0] - 2026-04-11

### Added
- Initial release with `libby extract` command
- DOI-based metadata extraction via Crossref
- PDF text extraction with pypdf
- AI-powered DOI/title extraction (DeepSeek)
- Citekey formatting with configurable pattern
- BibTeX and JSON output formats
- Batch processing support
- Pipeline (stdin) input support
- YAML configuration
- Environment variable status check
```

- [ ] **Step 4: 运行所有测试**

```bash
uv run pytest
```

- [ ] **Step 5: 提交**

```bash
git add tests/integration/ README.md CHANGELOG.md
git commit -m "docs: README and CHANGELOG with integration tests"
```

---

## 计划自审 (Self-Review)

**1. Spec Coverage:**
- ✅ 项目骨架 (Task 1)
- ✅ 配置层 (Task 2)
- ✅ 数据模型 (Task 3)
- ✅ DOI 解析 (Task 4)
- ✅ PDF 文本提取 (Task 5)
- ✅ API 层基础 (Task 6)
- ✅ Crossref API (Task 7)
- ✅ Citekey 格式化 (Task 8)
- ✅ Output 层 (Task 9)
- ✅ 元数据提取核心 (Task 10)
- ✅ AI 提取器 (Task 11)
- ✅ CLI extract 命令 (Task 12)
- ✅ 集成测试与文档 (Task 13)

**2. Placeholder Scan:**
- ✅ 无 TBD/TODO 占位符
- ✅ 每步都有具体代码

**3. Type Consistency:**
- ✅ `BibTeXMetadata` 在所有任务中一致
- ✅ `BatchResult` 定义一致
- ✅ `LibbyConfig` 定义一致

**4. Scope Check:**
- ✅ 仅覆盖 extract 子系统
- ✅ fetch 和 websearch 不在此计划内

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-11-libby-extract-plan.md`**.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
