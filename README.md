# libby

AI-friendly CLI tool for scholarly paper management.

## Features

- **extract**: Extract metadata from DOI, title, or PDF
- **fetch**: Download PDFs by DOI with source cascade
- **websearch**: Search academic databases

## Installation

```bash
# Clone and install with uv
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
libby extract paper.pdf --ai-extract  # Use AI for better extraction
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

### Fetch PDF by DOI

```bash
libby fetch 10.1007/s11142-016-9368-9
libby fetch 10.1007/s11142-016-9368-9 --dry-run  # Show URL only
libby fetch 10.1007/s11142-016-9368-9 --source unpaywall  # Use specific source
libby fetch 10.1007/s11142-016-9368-9 --source core       # CORE.ac.uk only
libby fetch 10.1007/s11142-016-9368-9 --source scihub     # Sci-hub only
```

Sources cascade order: Crossref OA → Unpaywall → Semantic Scholar → CORE → arXiv → PMC → bioRxiv → Sci-hub → Serpapi

**CORE.ac.uk**: Finds OA versions from institutional repositories worldwide (e.g., SMU ink.library, web.archive.org archives). Useful when publisher links return 403.

**Sci-hub Fallback**: When Sci-hub aiohttp request fails (blocked/CAPTCHA), automatically falls back to Selenium WebDriver (requires Chrome browser).

Output:
- `~/.lib/papers/{citekey}/{citekey}.pdf`
- `~/.lib/papers/{citekey}/{citekey}.bib`

### Web Search for Papers

Search across multiple academic databases in parallel:

```bash
libby websearch "machine learning"                  # Basic search
libby websearch "AI" --year-from 2023 --year-to 2025 # Year range
libby websearch "nature" --venue Nature              # Journal filter
libby websearch "10.1234/test"                       # DOI -> fetch fallback
libby websearch "quantum" --format json              # JSON output
libby websearch "physics" -o results.bib             # Save to file
libby websearch "biology" --no-serpapi               # Skip Serpapi
```

**Sources searched in parallel:**
- Crossref (bibliographic metadata)
- Semantic Scholar (AI paper database)
- Google Scholar (via scholarly package)
- Serpapi Google Scholar (optional, controlled usage)

**Default filters:**
- Year: current year - 2 (recent papers only)
- Results: 50 per source, merged by DOI
- Longer values kept when merging (title, abstract)

**Serpapi behavior:**
- Max 5 pages per search (50 results)
- Separate `_serpapi.json` output file
- Skip with `--no-serpapi` to save quota

**DOI fallback:**
If you provide a DOI instead of keywords, libby will:
1. Try to fetch the PDF
2. If fetch fails, extract metadata only

### Requirements for Sci-hub Selenium

- Chrome browser installed
- ChromeDriver (auto-managed by Selenium)

## Configuration

Create `~/.libby/config.yaml`:

```yaml
papers_dir: ~/.lib/papers
citekey:
  pattern: "{author}_{year}_{title}"
  author_words: 1
  title_words: 3
  title_chars_per_word: 0  # 0 = unlimited
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
```

## Environment Variables

| Variable | Purpose | Default Behavior |
|----------|---------|------------------|
| `S2_API_KEY` | Semantic Scholar API | 1 req/sec without key |
| `SERPAPI_API_KEY` | Google Scholar search | Skip if not set |
| `EMAIL` | Unpaywall access | Skip if not set |
| `DEEPSEEK_API_KEY` | AI extraction | Skip if not set |

## Testing

```bash
uv run pytest
```

## License

MIT