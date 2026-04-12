# Changelog

All notable changes to libby will be documented in this file.

## [0.4.0] - 2026-04-12

### Added
- **`libby websearch` command** for multi-source academic database search
  - Parallel search across Crossref, Semantic Scholar, Google Scholar
  - Serpapi Google Scholar (controlled, 5 pages max)
  - Unified SearchFilter with year_from, year_to, venue, issn options
  - DOI-based result merging (keep longer values, fill missing fields)
  - Output formats: BibTeX (default), JSON
  - DOI input triggers fetch -> extract fallback workflow
  - Serpapi extra file output (`{output}_serpapi.json`)
  - Rich table display for results

### Models
- `SearchFilter`: Unified filter model with year_from (default: current - 2), year_to, venue, issn
- `SearchResult`: Single result with DOI merging via `merge_from()` method
- `SearchResults`: Batch results with `to_json()` and `to_bibtex()` methods
- `SerpapiExtraInfo`: Serpapi-specific metadata (link, cited_by_count)

### API Extensions
- CrossrefAPI.search() - SearchFilter to Crossref native params
- SemanticScholarAPI.search() - SearchFilter to S2 native params
- ScholarlyAPI - Google Scholar wrapper via scholarly package
- SerpapiAPI.search() - Pagination (5 pages) + quota detection

### Dependencies
- scholarly (for Google Scholar search)

## [0.3.1] - 2026-04-11

### Added
- **CORE.ac.uk source** for institutional repository PDF access
  - Finds OA versions from repositories worldwide that Unpaywall doesn't track
  - Added to cascade: Crossref → Unpaywall → S2 → **CORE** → arXiv → PMC → bioRxiv → Sci-hub
  - New `--source core` option for single-source fetching

### Fixed
- Wiley paywall downloads (status 403) now fall back to CORE instead of failing

## [0.3.0] - 2026-04-11

### Added
- **Selenium-based Sci-hub downloader** for reliable PDF downloads when aiohttp fails
- Automatic fallback strategy: aiohttp first, then Selenium if blocked/CAPTCHA
- Citekey sanitization: invalid filesystem characters (<>:"/\\|?*) replaced with underscore

### Changed
- Removed `--free-proxy` option (FreeProxy library proved unreliable)
- Sci-hub now uses Selenium WebDriver as automatic fallback (requires Chrome browser)
- **Cascade logic fix**: each source gets URL → tries download → continues to next if download fails
  (Previously: stopped cascade once URL found, then tried download at CLI level)

### Dependencies
- selenium (for Sci-hub WebDriver downloads)
- aiofiles (for async file operations)

## [0.2.0] - 2026-04-11

### Added
- `libby fetch` command with PDF downloading by DOI
- Source cascade: Crossref OA → Unpaywall → Semantic Scholar → arXiv → PMC → bioRxiv → Sci-hub → Serpapi
- `--source` option to use specific source only
- `--dry-run` option to show PDF URL without downloading
- `--no-scihub` option to skip Sci-hub source
- CAPTCHA detection for Sci-hub with manual download instructions
- BibTeX output saved alongside downloaded PDFs

## [0.1.0] - 2026-04-11

### Added
- Initial release with `libby extract` command
- DOI-based metadata extraction via Crossref API
- Title-based metadata search (Crossref fallback)
- PDF text extraction with pypdf
- DOI parsing with line break handling
- AI-powered DOI/title extraction (DeepSeek API, optional)
- Citekey formatting with configurable pattern
- BibTeX and JSON output formats
- Batch processing for PDF directories
- Stdin pipeline support
- YAML configuration system
- Environment variable status check (S2_API_KEY, SERPAPI_API_KEY, EMAIL, DEEPSEEK_API_KEY)
- PDF file organization into `~/.lib/papers/{citekey}/`

### Configuration
- Default papers directory: `~/.lib/papers`
- Default citekey pattern: `{author}_{year}_{title}`
- Configurable via `~/.libby/config.yaml`

### Dependencies
- typer (CLI framework)
- rich (terminal output)
- pypdf (PDF extraction)
- aiohttp (async HTTP)
- aiolimiter (rate limiting)
- pyyaml (configuration)
- pydantic (data validation)
- openai (AI extraction)
- scholarly (Google Scholar, optional)