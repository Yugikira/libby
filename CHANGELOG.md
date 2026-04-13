# Changelog

All notable changes to libby will be documented in this file.

## [0.5.2] - 2026-04-13

### Changed
- **Semantic Scholar rate limits differentiated by API key presence**
  - With API key: 1 req/sec (docs: 300 req/5 min)
  - Without key: 1 req/3 sec (docs: 100 req/5 min)
- **Default year filter fixed across all API modules**
  - Crossref, S2, Scholarly now set `year_from = current_year - 2` when filter is None

## [0.5.1] - 2026-04-13

### Security
- **SSRF protection**: Add URL validation in PDF downloads
  - Block internal/private IP addresses
  - Enforce http/https scheme only
  - Add file size limit (50 MB max)
  - Warning for non-trusted domains
- **New module**: `libby/utils/url_validation.py` with `is_valid_pdf_url()`

### Fixed
- **Session leak in base API**: Add lock for race condition prevention, proper timeout config
- **WebDriver leak in Serpapi**: Use try/finally to ensure driver.quit() is always called
- **WebDriver leak in Scihub**: Add proper cleanup on exceptions, refactor error handling
- **DOI normalization**: Add missing `http://doi.org/` prefix handling
- **Null display**: Add `N/A` fallback for `pdf_path` in fetch result display

### Refactored
- **ScihubDownloader**: Extract `_ensure_driver()` helper for cleaner initialization
- **BaseAPIClient**: Add 5xx error handling, ClientException catch, proper 429 retry flow

## [0.5.0] - 2026-04-13

### Changed
- **Unified --serpapi parameter across all commands**
  - Values: `deny` (default), `ask`, `auto`
  - `deny`: Never use Serpapi (safest for quota)
  - `ask`: Prompt user for confirmation (single input only)
  - `auto`: Auto-use Serpapi without confirmation (batch mode)
  - `--source serpapi`: Bypasses all policies and uses Serpapi directly
  - Replaced `--no-serpapi` flag with `--serpapi deny` in websearch
  - Removed ad-hoc Serpapi confirmation in fetch; now controlled by policy

### Removed
- **`--no-serpapi` flag in websearch**: Use `--serpapi deny` instead

## [0.4.5] - 2026-04-13

### Added
- **Title search cascade: Crossref → S2 → Serpapi**
  - S2 fallback when Crossref returns no results
  - Serpapi fallback (requires user confirmation or `--serpapi` flag)
  - `SerpapiSearchNeeded` exception prompts user for Serpapi usage
- **Scanned PDF support: `--with-doi` and `--with-title`**
  - Provide DOI/title for PDFs that cannot extract text (scanned documents)
  - Batch input: `pdf_path|doi` or `pdf_path|title` format with `|` separator
  - Pipe stdin support: `echo "pdf.pdf|doi" | libby extract`
- **`abstract` field in BibTeXMetadata**
  - Optional abstract field for paper summaries
  - BibTeX output includes abstract when available
- **Unified lib_dir configuration**
  - Single `lib_dir` config (`~/.lib`) with auto-generated subdirectories:
    - `papers/`: PDF files and BibTeX metadata
    - `extract_task/`: Failed extraction task logs
    - `search_results/`: Websearch output files
  - Simplified config: one base path instead of multiple paths

### Changed
- **PMC PDF URL format**: `/pdf/main.pdf` instead of `/pdf/`
  - Avoids 301 redirect issues with aiohttp
  - Note: PMC uses reCAPTCHA, aiohttp downloads may still fail
- **extract CLI parameter**: `--serpapi` to auto-enable Serpapi in batch mode

### Fixed
- **Serpapi metadata extraction**: Proper BibTeX fetching via `serpapi_cite_link`
  - Complete metadata (journal, volume, pages) from BibTeX
  - Fallback to basic fields if BibTeX fetch fails

## [0.4.4] - 2026-04-13

### Added
- **Detailed failure reporting for fetch**
  - `source_attempts` tracking: each source URL, status, and error
  - `_attempts.json` file saved on failure with all cascade attempts
  - Display found URLs that were blocked (helps manual download)
- **Always save `.bib` file**: even when PDF download fails (metadata already extracted)

### Changed
- **`--no-scihub` now correctly skips Sci-hub in cascade** (previously still attempted)

### Fixed
- Remove punctuation from title words in citekey formatting
- Close serpapi session in PDFFetcher.close()
- `SerpapiConfirmationNeeded` message shows found URLs

## [0.4.3] - 2026-04-13

### Added
- **Environment variables in YAML config**
  - `semantic_scholar.api_key` - alternative to S2_API_KEY env var
  - `serpapi.api_key` - alternative to SERPAPI_API_KEY env var
  - `unpaywall.email` - alternative to EMAIL env var
  - `ai_extractor.api_key` - alternative to DEEPSEEK_API_KEY env var
  - Config file values take precedence over environment variables
- **Stdin pipeline for fetch** (`cat dois.txt | libby fetch`)
- **`--source serpapi` for fetch**: Direct Serpapi search without cascade confirmation

### Changed
- **Unified source parameter naming**: `--source s2` for both fetch and websearch
  - Previously: fetch used `s2`, websearch used `semantic_scholar`
  - Now: both commands use `s2` consistently
- **Corrected S2_API_KEY rate limit info**: 1 req/sec (same with or without key)
- **Citekey formatting**: Remove punctuation from title words (comma, period, hyphen, etc.)

### Fixed
- **Semantic Scholar search fixes**
  - Remove invalid `issn` field from S2 API request (caused error)
  - Fix year filter: `year_from` now correctly converts to `year={from}-{current_year}` range
  - Parse journal nested object: extract `journal.name`, `volume`, `pages`
  - Journal fallback to `venue` field when `journal.name` is empty
- **Unclosed session warning**: Close serpapi session in PDFFetcher.close()

## [0.4.2] - 2026-04-13

### Added
- **Serpapi BibTeX integration** for complete metadata fetching
  - Fetch BibTeX via `serpapi_cite_link` from search results
  - Parse BibTeX to get complete fields (journal, volume, number, pages, publisher)
  - Add `parse_bibtex()` function for BibTeX string parsing
  - Selenium fallback for Google Scholar BibTeX 403 errors
  - Configurable parallel workers: `serpapi.max_bibtex_workers` (default: 5, max: 20)

### Changed
- `_parse_serpapi()` extracts basic fields (title, author, year) as fallback
- `SerpapiAPI.get_bibtex()` uses visible Chrome (headless detected by Google)
- `get_pdf_url()` only checks first result (most relevant)
- `_fetch_serpapi_bibtex()` uses Semaphore for limited parallelism

## [0.4.1] - 2026-04-12

### Added
- **Websearch improvements**
  - `--source` parameter for single-source search (crossref, semantic_scholar, scholarly, serpapi)
  - `--author` parameter for author name filtering
  - `--venue` and `--issn` journal resolution via Crossref Journals API
  - Default output path: `~/.lib/papers/search_results/yymmdd_{keywords}.bib`
  - Summary display: first 3 + last 3 results in table
  - `--no-save` option to skip file output

### Changed
- Author filtering strategy: post-filter for Crossref/S2, query helper for Scholarly/Serpapi
- Serpapi supports SearchFilter (year range via as_ylo/as_yhi, author/venue helpers)

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
