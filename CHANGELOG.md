# Changelog

All notable changes to libby will be documented in this file.

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