# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`libby` is a Python-based AI-friendly CLI tool for scholarly paper management. The current version covers three core functions: metadata extraction, PDF fetching, and web search.

Uses `uv` for environment management.

## Command Architecture

### `libby extract`

Retrieve metadata following BibTeX standard.

**Input sources:**
- DOI: Query Crossref directly
- Title: Crossref first, Semantic Scholar fallback, `scholarly` package final fallback
- PDF: Extract text from first page to find DOI/title, then fallback to DOI extraction

**Output:**
- BibTeX metadata with formatted citekey
- Default citekey format: `{first_author_family_name}_{year}_{first_three_content_words}`
- Content words exclude function words (the, a, do, does, are, is, etc.)

**File handling:**
- Default folder: `~/.lib/papers/{citekey}/`
- Renames and moves PDF + metadata to folder
- Use `--copy` to preserve original file

### `libby fetch`

Download PDF by DOI with source cascade.

**Resolution order:**
1. Crossref OA link (if available)
2. Unpaywall
3. Semantic Scholar `openAccessPdf`
4. arXiv (if ArXiv ID found)
5. PubMed Central
6. bioRxiv/medRxiv
7. Sci-hub (papers before 2022 only)
8. Serpapi Google Scholar (manual trigger, requires user permission - not free)

**Default path:** `~/.lib/papers/temp/`

### `libby websearch`

Search for paper metadata with keywords or semantic queries.

**Sources (parallel execution):**
- Crossref: `query.bibliographic` + filter params (from-pub-date, issn)
- Semantic Scholar: `paper/search` endpoint + year/venue params
- Google Scholar: scholarly package (sync wrapped in async)
- Serpapi: Controlled usage (max 5 pages, quota detection)

**Default filters:**
- year_from: current year - 2 (SearchFilter default)
- year_to: None
- venue/issn: Optional

**Filter conversion:**
- Crossref: filter=from-pub-date:{year},issn:{issn}
- Semantic Scholar: year={from}-{to}, venue={name}
- Scholarly: after:{year}, before:{year}, source:{venue}

**Result merging:**
- Results with same DOI merged via `SearchResult.merge_from()`
- Longer values kept (title, abstract)
- Missing fields filled from other sources
- Sources list combined (crossref, semantic_scholar, google_scholar)

**DOI fallback:**
If query is a DOI, triggers fetch -> extract workflow instead of search.

**Serpapi behavior:**
- Runs separately after parallel sources
- Max 5 pages, 2 retries per page
- Returns (results, quota_reached) tuple
- Extra info saved to `_serpapi.json`

## Environment Variables

| Variable | Purpose | Behavior if missing |
|----------|---------|---------------------|
| `S2_API_KEY` | Semantic Scholar API key | Same rate limit (1 req/sec) |
| `SERPAPI_API_KEY` | Serpapi endpoint | Skip Google Scholar Serpapi method |
| `EMAIL` | Unpaywall access | Skip Unpaywall queries |

Check environment variables at startup with green/red status indicators.

## Error Handling

For server errors (500/503):
- Retry with timeout
- Maximum retries: 3 (configurable)
- Applies to extract, fetch, websearch operations

## Testing

Use these fixtures for testing:
- DOI: `https://doi.org/10.1007/s11142-016-9368-9`
- PDF: `./example/test.pdf`
- Query: `"corporate site visit"`

## Documentation Requirements

On every change:
1. Update `CHANGELOG.md` for major changes
2. Update `./skills/SKILL.md`
3. Update `README.md`

## Reference Code

- `reference/paperfetch.py`: Legal OA PDF fetching implementation (stdlib only)
- `reference/doi_hunter/`: Sci-hub downloading with proxy handling
- `reference/rest-api-doc/`: Crossref REST API documentation

Crossref API etiquette: Include `mailto:` in User-Agent header or `mailto` parameter for polite pool access (better performance).

## Notes

- Use `chrome-dev-tools` MCP to read reference websites if `WebFetch` fails
- Sci-hub domain may change - verify currently available site before implementation
