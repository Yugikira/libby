# libby

AI-friendly CLI tool for scholarly paper management.

## Features

- **extract**: Extract metadata from DOI, title, or PDF
- **fetch**: Download PDFs from OA sources (coming in v0.2)
- **websearch**: Search academic databases (coming in v0.3)

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