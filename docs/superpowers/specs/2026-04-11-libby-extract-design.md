# libby Design Document

**Date**: 2026-04-11
**Author**: Yugi + Claude
**Status**: Draft - Pending User Review

---

## 1. Project Overview

`libby` is a Python-based **AI-friendly** CLI tool for scholarly paper management. The current version (v0.1.0) covers three core functions:

1. **extract** - Metadata extraction from DOI, title, or PDF
2. **fetch** - PDF downloading from multiple OA sources
3. **websearch** - Paper metadata search across academic databases

This document covers the design for the **extract** subsystem (Phase 1), with fetch and websearch to follow in subsequent phases.

---

## 2. Architecture

### 2.1 Module Structure

```
libby/
├── __init__.py
├── __main__.py          # CLI entry point (typer app)
├── cli/
│   ├── __init__.py
│   ├── extract.py       # libby extract command
│   ├── fetch.py         # libby fetch command (Phase 2)
│   ├── websearch.py     # libby websearch command (Phase 3)
│   └── utils.py         # CLI utilities (stdin, batch processing)
├── core/
│   ├── __init__.py
│   ├── metadata.py      # Metadata extraction logic
│   ├── pdf_fetcher.py   # PDF downloading logic (Phase 2)
│   ├── citekey.py       # Citekey formatting
│   ├── pdf_text.py      # PDF text extraction (pypdf)
│   └── ai_extractor.py  # AI-powered DOI/title extraction
├── api/
│   ├── __init__.py
│   ├── base.py          # Async HTTP client base (rate limit)
│   ├── crossref.py      # Crossref API
│   ├── semantic_scholar.py
│   ├── unpaywall.py
│   ├── arxiv.py
│   ├── pmc.py
│   ├── biorxiv.py
│   ├── scihub.py        # Sci-hub (optional, pre-2022)
│   ├── serpapi.py       # Serpapi Google Scholar
│   └── scholarly.py     # scholarly package wrapper
├── config/
│   ├── __init__.py
│   ├── loader.py        # YAML config loading
│   ├── defaults.py      # Default values
│   └── env_check.py     # Environment variable status
├── utils/
│   ├── __init__.py
│   ├── retry.py         # Retry logic (5-phase strategy)
│   ├── file_ops.py      # File operations (move, rename)
│   └── doi_parser.py    # DOI normalization/extraction
├── models/
│   ├── __init__.py
│   ├── metadata.py      # BibTeXMetadata data model
│   ├── result.py        # BatchResult model
│   └── config.py        # Config models
└── output/
    ├── __init__.py
    ├── bibtex.py        # BibTeX format
    ├── ris.py           # RIS format
    ├── json.py          # JSON format
    ├── text.py          # Plain text format
```

### 2.2 Design Principles

- **Isolation**: Each module has one clear purpose and communicates through well-defined interfaces
- **Async-first**: Batch operations use `aiohttp` with strict rate limiting
- **Configuration-driven**: User preferences via YAML config with sensible defaults
- **AI-friendly**: JSON output option for pipeline integration; optional AI extraction

---

## 3. API Layer Design

### 3.1 Async HTTP Client Base

All API clients inherit from a base class that enforces rate limits:

```python
# api/base.py
from aiolimiter import AsyncLimiter

class AsyncAPIClient:
    """Async HTTP client with rate limit control"""

    def __init__(self, rate_limit: RateLimit):
        self._limiter = AsyncLimiter(rate_limit.requests, rate_limit.period)
        self._session: aiohttp.ClientSession | None = None

    async def get(self, url: str, **kwargs) -> dict:
        await self._limiter.acquire()
        async with self._session.get(url, **kwargs) as resp:
            if resp.status == 429:
                await self._handle_rate_limit_retry(url, **kwargs)
            return await resp.json()
```

### 3.2 Rate Limit Configuration

| API | Rate Limit | Notes |
|-----|------------|-------|
| Crossref | 1 req/sec | Polite pool with mailto |
| Semantic Scholar | 1 req/sec | Always, even with API key |
| Unpaywall | No explicit limit | Requires EMAIL |
| arXiv | 3 req/sec | Recommended delay |
| PMC | No explicit limit | Recommended delay |

### 3.3 Retry Strategy (Server Errors)

**5-phase retry for 500/503 errors**:

- Phase 1: 3 quick retries (delays: 1s, 2s, 4s)
- Phase 2: 1 retry after 15s
- Phase 3: 1 retry after 60s
- Total: 5 retries max

If all retries fail:
1. Record in `failed_tasks.json`
2. Alert user with summary
3. Continue with remaining tasks (batch mode)

---

## 4. Configuration Layer

### 4.1 YAML Config Structure

```yaml
# ~/.libby/config.yaml (default location)

papers_dir: ~/.lib/papers

citekey:
  pattern: "{author}_{year}_{title}"
  author_words: 1
  title_words: 3
  title_chars_per_word: 0  # 0 = no limit, >0 = max chars per word
  case: lowercase
  ascii_only: true
  ignored_words:
    - the - a - an - of - for - in - at - to - and
    - do - does - is - are - was - were - be - been
    - that - this - these - those - on - by - with - from

retry:
  max_retries: 5
  delays: [1, 2, 4, 15, 60]

ai_extractor:
  api_key: null
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 1000
```

### 4.2 Config Loading Priority

1. CLI `--config /path/to/config.yaml` (highest)
2. Environment variable `LIBBY_CONFIG=/path/to/config.yaml`
3. Default `~/.libby/config.yaml` (lowest)

### 4.3 Environment Variable Status Check

At startup, display status for:
- `S2_API_KEY` - Semantic Scholar (green = 1 req/sec, red = same)
- `SERPAPI_API_KEY` - Serpapi (green = available, red = skip)
- `EMAIL` - Unpaywall (green = available, red = skip)
- `DEEPSEEK_API_KEY` - AI extractor (green = available, red = skip)

---

## 5. Core Layer - Metadata Extraction

### 5.1 Extraction Flow

```python
# core/metadata.py
class MetadataExtractor:
    async def extract_from_doi(self, doi: str) -> BibTeXMetadata:
        data = await self.crossref.fetch_by_doi(doi)
        return self._parse_crossref_to_bibtex(data)

    async def extract_from_title(self, title: str) -> BibTeXMetadata:
        # Cascade: Crossref -> S2 -> scholarly
        result = await self.crossref.search_by_title(title)
        if result: return self._parse(result[0])

        result = await self.s2.search_by_title(title)
        if result: return self._parse(result)

        result = await self.scholarly.search_by_title(title)
        if result: return self._parse(result)

        raise MetadataNotFoundError(f"Title not found: {title}")

    async def extract_from_pdf(self, pdf_path: Path, use_ai: bool = False) -> BibTeXMetadata:
        text = extract_first_page_text(pdf_path)

        if use_ai:
            result = await self.ai_extractor.extract_from_text(text)
            if result["doi"]: return await self.extract_from_doi(result["doi"])
            if result["title"]: return await self.extract_from_title(result["title"])

        # Regex fallback
        doi = extract_doi_from_text_regex(text)
        if doi: return await self.extract_from_doi(doi)

        title = extract_title_from_text(text)  # heuristic
        if title: return await self.extract_from_title(title)

        raise MetadataNotFoundError(f"No DOI/Title in PDF: {pdf_path}")
```

### 5.2 DOI Parsing

```python
# utils/doi_parser.py
def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("doi.org/")
    doi = doi.removeprefix("DOI:")
    doi = doi.removeprefix("doi:")
    return doi.lower()

def extract_doi_from_text_regex(text: str) -> str | None:
    # Handle line breaks in DOI
    merged = re.sub(r'-\n', '-', text)
    merged = re.sub(r'\n', ' ', merged)
    pattern = r'(10\.\d{4,}/[^\s]+)'
    match = re.search(pattern, merged)
    return match.group(1) if match else None
```

### 5.3 PDF Text Extraction

```python
# core/pdf_text.py
from pypdf import PdfReader

def extract_first_page_text(pdf_path: Path) -> str:
    reader = PdfReader(pdf_path)
    if not reader.pages: return ""
    return reader.pages[0].extract_text()
```

### 5.4 AI-Powered Extraction

```python
# core/ai_extractor.py
class AIExtractor:
    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, config: Config):
        self.api_key = config.ai_extractor.api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ConfigError("AI extractor requires api_key")

        self.base_url = config.ai_extractor.base_url or self.DEFAULT_BASE_URL
        self.model = config.ai_extractor.model or self.DEFAULT_MODEL

    async def extract_from_text(self, text: str) -> dict:
        prompt = f"""Extract DOI and title from this paper text.
Return JSON: {"doi": "xxx", "title": "xxx"}
If not found: {"doi": null, "title": null}

Text (first 2000 chars):
{text[:2000]}"""

        response = await self._call_openai_api(prompt)
        return json.loads(response)
```

---

## 6. Citekey Formatting

### 6.1 Formatter Logic

```python
# core/citekey.py
class CitekeyFormatter:
    def format(self, metadata: BibTeXMetadata) -> str:
        author = self._format_author(metadata.author)
        title = self._format_title(metadata.title)
        year = str(metadata.year)

        result = self.pattern.format(author=author, title=title, year=year)

        if self.case == "lowercase": result = result.lower()
        elif self.case == "camelcase": result = self._to_camelcase(result)

        if self.ascii_only: result = self._to_ascii(result)

        return result

    def _format_author(self, author: str | list[str]) -> str:
        if isinstance(author, list):
            author = author[0] if author else "unknown"
        parts = author.split(",")
        return parts[0].strip() if parts else author.split()[-1]

    def _format_title(self, title: str) -> str:
        words = [w for w in title.split()
                 if w.lower() not in self.ignored_words]
        words = words[:self.title_words]
        if self.title_chars_per_word:
            words = [w[:self.title_chars_per_word] for w in words]
        return "_".join(words)
```

### 6.2 Default Output Example

Input: `DOI: 10.1007/s11142-016-9368-9`
Output citekey: `stent_2016_earnings_management_consequences`

---

## 7. Output Layer

### 7.1 Format Interface

```python
# output/base.py
class OutputFormatter(Protocol):
    def format(self, metadata: BibTeXMetadata) -> str: ...
    def format_batch(self, metadata_list: list[BibTeXMetadata]) -> str: ...
```

### 7.2 BibTeX Output

```python
# output/bibtex.py
class BibTeXFormatter:
    def format(self, metadata: BibTeXMetadata) -> str:
        return f"""@{metadata.entry_type}{{{metadata.citekey},
  author = {{{self._format_authors(metadata.author)}}},
  title = {{{metadata.title}}},
  year = {{{metadata.year}}},
  doi = {{{metadata.doi}}},
}}"""
```

### 7.3 JSON Output

```python
# output/json.py
class JSONFormatter:
    def format_batch(self, metadata_list: list[BibTeXMetadata]) -> str:
        return json.dumps([m.to_dict() for m in metadata_list])
```

---

## 8. File Handling

### 8.1 PDF Organization

```python
# utils/file_ops.py
class FileHandler:
    def organize_pdf(self, pdf_path: Path, metadata: BibTeXMetadata, copy: bool = False) -> Path:
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

### 8.2 Batch Processing

```python
# cli/utils.py
async def process_pdf_batch(pdf_dir: Path, ...) -> BatchResult:
    pdf_files = list(pdf_dir.glob("*.pdf"))
    results = BatchResult()

    for pdf_path in pdf_files:
        try:
            metadata = await extractor.extract_from_pdf(pdf_path, use_ai=ai_extract)
            file_handler.organize_pdf(pdf_path, metadata, copy=copy)
            results.succeeded.append({"pdf": str(pdf_path), "citekey": metadata.citekey})
        except Exception as e:
            results.failed.append({"pdf": str(pdf_path), "error": str(e)})

    return results
```

### 8.3 Stdin Pipeline

```python
def read_stdin_lines() -> list[str]:
    if sys.stdin.isatty(): return []
    return [line.strip() for line in sys.stdin if line.strip()]
```

---

## 9. CLI Commands

### 9.1 Main Entry

```python
# __main__.py
import typer

app = typer.Typer(name="libby", help="AI-friendly CLI for paper management")

app.add_typer(extract_app, name="extract")
app.add_typer(fetch_app, name="fetch")
app.add_typer(websearch_app, name="websearch")
```

### 9.2 `libby extract`

```python
@extract_app.command()
def extract(
    input: str = typer.Argument(None, help="DOI, title, or PDF path"),
    batch_dir: Path = typer.Option(None, "--batch-dir", help="Directory of PDFs"),
    output: Path = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("bibtex", "--format", "-f"),
    copy: bool = typer.Option(False, "--copy"),
    ai_extract: bool = typer.Option(False, "--ai-extract"),
    config_path: Path = typer.Option(None, "--config"),
):
    # Load config, init components
    # Gather inputs (argument + batch_dir + stdin)
    # Process batch
    # Output results
    # Save failed tasks if any
```

**Usage Examples**:
```bash
libby extract 10.1007/s11142-016-9368-9
libby extract "corporate site visit" --format json
libby extract ./paper.pdf --ai-extract
libby extract --batch-dir ./papers/ --output results.bib
cat dois.txt | libby extract
```

---

## 10. Dependencies

### 10.1 pyproject.toml

```toml
[project]
name = "libby"
version = "0.1.0"
requires-python = ">=3.10"

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
```

---

## 11. Error Handling

- **404 Not Found**: Return empty result, no retry
- **429 Too Many Requests**: Wait and retry (respect rate limit)
- **500/503 Server Error**: 5-phase retry strategy
- **Validation Error**: Exit with code 3, show error message
- **Runtime Error**: Exit with code 1, show summary

---

## 12. Testing Fixtures

As specified in CLAUDE.md:
- DOI: `https://doi.org/10.1007/s11142-016-9368-9`
- PDF: `./example/test.pdf`
- Query: `"corporate site visit"`

---

## 13. Future Phases

### Phase 2: `libby fetch`
- PDF downloading cascade: Crossref OA → Unpaywall → S2 → arXiv → PMC → bioRxiv → Sci-hub
- Serpapi Google Scholar (requires user permission)

### Phase 3: `libby websearch`
- Crossref keyword search (default: recent 2 years, 50 results)
- Semantic Scholar semantic search
- Google Scholar (scholarly package, Serpapi fallback)
- Deduplication by DOI

---

## 14. Documentation Requirements

On every change:
1. Update `CHANGELOG.md` for major changes
2. Update `./skills/SKILL.md`
3. Update `README.md`