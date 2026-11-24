# libby

Python AI-friendly CLI tool for scholarly paper management: metadata extraction (`extract`), PDF fetching (`fetch`), and academic search (`websearch`).

## Commands (`uv`)

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv tool install --reinstall .
```

## Layout

- `src/libby/cli/` — Typer CLI commands (`extract`, `fetch`, `websearch`).
- `src/libby/core/` — Core workflows (metadata extraction, citekey formatting, PDF fetcher cascade, parallel websearch merging).
- `src/libby/api/` — External API adapters (Crossref, Semantic Scholar, Unpaywall, arXiv, PMC, bioRxiv, Sci-hub, SerpAPI).
- `src/libby/config/`, `src/libby/models/`, `src/libby/output/`, `src/libby/utils/` — Config, Pydantic models, BibTeX/JSON formatters, DOI/retry helpers.
- `tests/` — Unit and integration tests (`tests/conftest.py`).
- `docs/` — Design specs, plans, and [demand.md](docs/demand.md).

## Command Architecture & Invariants

- **`libby extract`:** DOI -> Crossref; Title -> Crossref then Semantic Scholar; PDF -> first-page text extraction -> DOI fallback. Default citekey: `{first_author_family_name}_{year}_{first_three_content_words}` (excluding function words). Default folder: `~/.lib/papers/{citekey}/` (`--copy` preserves original).
- **`libby fetch`:** Cascade order: Crossref OA -> Unpaywall -> Semantic Scholar `openAccessPdf` -> arXiv -> PubMed Central -> bioRxiv/medRxiv -> Sci-hub (pre-2022 only) -> SerpAPI Google Scholar (manual/paid, requires user permission). Default folder: `~/.lib/papers/temp/`.
- **`libby websearch`:** Parallel Crossref + Semantic Scholar, then separate SerpAPI pass (max 5 pages, 2 retries/page, quota detection, extra info in `_serpapi.json`). Default `year_from = current_year - 2`. Merge same-DOI results via `SearchResult.merge_from()` (keep longer title/abstract, fill missing fields, combine `sources`). DOI queries fall back to `fetch -> extract`.
- **Retries & etiquette:** Retry HTTP 500/503 up to 3 times (configurable). Include `mailto:` in Crossref requests for polite pool access.
- **Env vars** (checked at startup): `S2_API_KEY` (Semantic Scholar), `SERPAPI_API_KEY` (skip SerpAPI if missing), `EMAIL` (skip Unpaywall if missing).
- **Docs sync:** Update `CHANGELOG.md` and `README.md` on major changes.
