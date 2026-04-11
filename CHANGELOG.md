# Changelog

All notable changes to libby will be documented in this file.

## [0.3.0] - 2026-04-11

### Added
- **Selenium-based Sci-hub downloader** for reliable PDF downloads when aiohttp fails
- Automatic fallback strategy: aiohttp first, then Selenium if blocked/CAPTCHA
- Download fallback: if PDF URL download fails, automatically retry with Sci-hub Selenium
- Citekey sanitization: invalid filesystem characters (<>:"/\\|?*) replaced with underscore

### Changed
- Removed `--free-proxy` option (FreeProxy library proved unreliable)
- Sci-hub now uses Selenium WebDriver as automatic fallback (requires Chrome browser)
- PDF downloads are more reliable due to multi-layer fallback strategy

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