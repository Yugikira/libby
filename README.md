# libby

AI-friendly CLI tool for scholarly paper management.

## Features

- **extract**: Extract metadata from DOI, title, or PDF
- **fetch**: Download PDFs by DOI with source cascade
- **websearch**: Search academic databases with multi-source parallel execution

## Installation

```bash
# Clone and install with uv
git clone https://github.com/your-username/libby
cd libby
uv sync
```

## Configuration

Create `~/.libby/config.yaml` for customization:

```yaml
# Base directory for all paper files
papers_dir: ~/.lib/papers

# Environment variables (alternative to system env vars)
# You can configure API keys here instead of setting environment variables
semantic_scholar:
  api_key: "your-s2-api-key-here"    # Optional: S2_API_KEY env var alternative

serpapi:
  api_key: "your-serpapi-key-here"   # Optional: SERPAPI_API_KEY env var alternative
  max_bibtex_workers: 5              # Parallel workers for BibTeX fetch (default: 5)
  max_workers_limit: 20              # Maximum allowed workers (safety limit)

unpaywall:
  email: "your-email@example.com"    # Optional: EMAIL env var alternative

ai_extractor:
  api_key: "your-deepseek-key-here"  # Optional: DEEPSEEK_API_KEY env var alternative
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 1000

# Citekey formatting configuration
citekey:
  pattern: "{author}_{year}_{title}"
  author_words: 1        # First author surname only
  title_words: 3         # First 3 content words
  title_chars_per_word: 0  # 0 = unlimited chars per word
  case: lowercase        # lowercase, uppercase, or original
  ascii_only: true       # Replace non-ASCII with underscore
  ignored_words:         # Words excluded from title
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
```

### Environment Variables Configuration

You can configure API keys and email in **two ways**:

1. **System environment variables** (recommended for security):
   ```bash
   export S2_API_KEY="your-key"
   export SERPAPI_API_KEY="your-key"
   export EMAIL="your-email@example.com"
   export DEEPSEEK_API_KEY="your-key"
   ```

2. **YAML config file** (`~/.libby/config.yaml`):
   ```yaml
   semantic_scholar:
     api_key: "your-s2-api-key"
   serpapi:
     api_key: "your-serpapi-key"
   unpaywall:
     email: "your-email@example.com"
   ai_extractor:
     api_key: "your-deepseek-key"
   ```

**Priority**: Config file values take precedence over environment variables.

### Configuration Fields Explained

| Field | Description | Default |
|-------|-------------|---------|
| `papers_dir` | Base directory for PDFs and metadata | `~/.lib/papers` |
| `citekey.pattern` | Citekey template: `{author}`, `{year}`, `{title}` | `{author}_{year}_{title}` |
| `citekey.author_words` | Number of author surname words | 1 |
| `citekey.title_words` | Number of title content words | 3 |
| `citekey.ignored_words` | Words excluded from title | Common function words |
| `serpapi.max_bibtex_workers` | Parallel BibTeX fetch workers | 5 |
| `semantic_scholar.api_key` | S2 API key (or use env var) | None |
| `serpapi.api_key` | Serpapi key (or use env var) | None |
| `unpaywall.email` | Email for Unpaywall (or use env var) | None |
| `ai_extractor.api_key` | DeepSeek key (or use env var) | None |

### Environment Variables Reference

| Variable | YAML Alternative | Purpose | Behavior if missing |
|----------|------------------|---------|---------------------|
| `S2_API_KEY` | `semantic_scholar.api_key` | Semantic Scholar API | Strict rate limit (1 req/sec) |
| `SERPAPI_API_KEY` | `serpapi.api_key` | Serpapi Google Scholar | Skip Serpapi search |
| `EMAIL` | `unpaywall.email` | Unpaywall API access | Skip Unpaywall queries |
| `DEEPSEEK_API_KEY` | `ai_extractor.api_key` | AI-powered PDF extraction | Skip AI extraction |

Check status at startup:

```bash
$ libby extract doi
[OK] S2_API_KEY: Semantic Scholar API enabled (1 req/sec with key)
[OK] SERPAPI_API_KEY: Serpapi enabled (Google Scholar fallback)
[OK] EMAIL: Unpaywall enabled (OA PDF lookup)
[OK] DEEPSEEK_API_KEY: AI Extractor enabled (PDF DOI/title extraction)
```

## Usage Examples

### For Human Reader

Basic operations with readable output:

```bash
# Extract metadata from DOI
libby extract 10.1007/s11142-016-9368-9

# Extract from PDF with AI assistance
libby extract paper.pdf --ai-extract

# Batch process PDF directory
libby extract --batch-dir ./papers/

# Pipeline input
echo "10.1007/s11142-016-9368-9" | libby extract
cat dois.txt | libby extract

# Fetch PDF by DOI
libby fetch 10.1007/s11142-016-9368-9
libby fetch 10.1007/s11142-016-9368-9 --dry-run  # Show URL only

# Batch fetch from file or stdin
libby fetch --batch dois.txt
cat dois.txt | libby fetch

# Use specific source only
libby fetch 10.1007/s11142-016-9368-9 --source unpaywall
libby fetch 10.1007/s11142-016-9368-9 --source core
libby fetch 10.1007/s11142-016-9368-9 --source scihub

# Web search with filters
libby websearch "machine learning"
libby websearch "AI" --year-from 2023 --year-to 2025
libby websearch "corporate governance" --author Smith --venue Nature
libby websearch "deep learning" --source s2

# Save results to file
libby websearch "quantum physics" -o results.bib
libby websearch "biology" --format json -o results.json
```

### For Agentic AI

Machine-readable JSON output with jq integration:

```bash
# Extract DOI -> JSON -> jq parse
libby extract 10.1007/s11142-016-9368-9 --format json | jq '.title'

# Example output:
# "Accounting for the effects of location-specific and firm-specific factors"

# Get all fields for AI processing
libby extract 10.1007/s11142-016-9368-9 --format json | jq '{
  title: .title,
  authors: .author,
  year: .year,
  doi: .doi,
  journal: .journal
}'

# Extract from PDF -> JSON for LLM input
libby extract paper.pdf --format json | jq '.abstract'

# Batch extract -> JSON array
libby extract --batch-dir ./papers/ --format json | jq '.[].title'

# Web search -> JSON -> filter by year
libby websearch "machine learning" --format json --no-save | jq '.results[] | select(.year >= 2023)'

# Web search -> JSON -> extract DOI list
libby websearch "AI forecasting" --format json --no-save | jq '.results[].doi'

# Web search -> JSON -> get first result details
libby websearch "corporate site visit" --format json --no-save | jq '.results[0] | {
  title: .title,
  doi: .doi,
  year: .year,
  journal: .journal,
  authors: .author | join(", ")
}'

# Combine search + fetch workflow (AI agent pattern)
libby websearch "quantum computing" --format json --no-save \
  | jq -r '.results[0].doi' \
  | xargs -I {} libby fetch {} --dry-run

# Search -> extract metadata workflow
libby websearch "nature climate" --format json --no-save \
  | jq -r '.results[:3][] | .doi' \
  | while read doi; do libby extract "$doi" --format json; done \
  | jq -s '[.[] | {doi, title, year}]'
```

**JSON Output Structure (websearch):**

```json
{
  "query": "machine learning",
  "total": 25,
  "results": [
    {
      "doi": "10.1234/example",
      "title": "Paper Title",
      "author": ["First Author", "Second Author"],
      "year": 2023,
      "journal": "Journal Name",
      "volume": "10",
      "number": "2",
      "pages": "100-120",
      "abstract": "Paper abstract text...",
      "sources": ["crossref", "s2"]
    }
  ],
  "sources_used": ["crossref", "s2", "scholarly"]
}
```

**JSON Output Structure (extract):**

```json
{
  "doi": "10.1007/s11142-016-9368-9",
  "title": "Accounting for the effects of location-specific...",
  "author": ["Author 1", "Author 2"],
  "year": 2016,
  "journal": "Review of Accounting Studies",
  "volume": "21",
  "number": "4",
  "pages": "1153-1191",
  "abstract": "Abstract text...",
  "citekey": "author_2016_accounting_effects"
}
```

## Source Cascade (fetch)

Order: Crossref OA → Unpaywall → Semantic Scholar → CORE → arXiv → PMC → bioRxiv → Sci-hub → Serpapi

**CORE.ac.uk**: Finds OA versions from institutional repositories worldwide (SMU ink.library, web.archive.org). Useful when publisher links return 403.

**Sci-hub Fallback**: Automatic Selenium WebDriver when aiohttp fails (blocked/CAPTCHA). Requires Chrome browser.

## Web Search Sources

**Parallel sources:**
- Crossref: Bibliographic metadata + ISSN filtering
- Semantic Scholar: AI paper database + abstracts
- Google Scholar: via scholarly package (free)

**Optional source:**
- Serpapi: Controlled Google Scholar (max 5 pages, BibTeX fetch)
  - `--no-serpapi` to skip and save quota
  - `--source serpapi` to use only Serpapi

**Single source mode:**
```bash
libby websearch "AI" --source crossref        # Crossref only
libby websearch "AI" --source s2  # S2 only
libby websearch "AI" --source scholarly        # Google Scholar only
libby websearch "AI" --source serpapi          # Serpapi only
```

## Requirements

- Python 3.10+
- Chrome browser (for Sci-hub Selenium fallback)
- ChromeDriver (auto-managed by Selenium)

## Testing

```bash
uv run pytest
```

## License

MIT