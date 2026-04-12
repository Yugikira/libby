# libby websearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement multi-source academic database search with parallel execution, field merging, and unified filter translation.

**Architecture:** WebSearcher orchestrates parallel search across Crossref/Semantic Scholar/Scholarly, Serpapi runs separately, SearchFilter translates user parameters to native API filters.

**Tech Stack:** aiohttp (async HTTP), asyncio.gather (parallel execution), scholarly (Google Scholar - already in deps), typer (CLI), rich (progress/table display).

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `libby/models/search_filter.py` | Unified filter model for multi-API translation | Create |
| `libby/models/search_result.py` | SearchResult, SearchResults, SerpapiExtraInfo | Create |
| `libby/api/crossref.py` | Extend with search() method | Modify |
| `libby/api/semantic_scholar.py` | Extend with search() method | Modify |
| `libby/api/scholarly.py` | Google Scholar scholarly package wrapper | Create |
| `libby/api/serpapi.py` | Extend with search() method (pagination + quota) | Modify |
| `libby/core/websearch.py` | WebSearcher orchestrator | Create |
| `libby/cli/websearch.py` | CLI command with DOI fallback | Create |
| `libby/__main__.py` | Register websearch command | Modify |

---

## Task Overview

| Task | Component | Test File |
|------|-----------|-----------|
| 1 | SearchFilter model | `tests/models/test_search_filter.py` |
| 2 | SearchResult model | `tests/models/test_search_result.py` |
| 3 | Crossref search extension | `tests/api/test_crossref.py` (extend) |
| 4 | Semantic Scholar search extension | `tests/api/test_semantic_scholar.py` (extend) |
| 5 | Scholarly wrapper | `tests/api/test_scholarly.py` |
| 6 | Serpapi search extension | `tests/api/test_serpapi.py` (extend) |
| 7 | WebSearcher core | `tests/core/test_websearch.py` |
| 8 | CLI websearch command | `tests/cli/test_websearch.py` |
| 9 | CLI registration | Manual test |
| 10 | Integration tests | `tests/integration/test_websearch.py` |
| 11 | Documentation updates | README, CHANGELOG, CLAUDE.md |

---

### Task 1: SearchFilter Model

**Files:**
- Create: `libby/models/search_filter.py`
- Create: `tests/models/test_search_filter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/models/test_search_filter.py
"""Tests for SearchFilter model."""

from libby.models.search_filter import SearchFilter
from datetime import datetime


def test_search_filter_defaults():
    """Test default year_from is 2 years ago."""
    filter = SearchFilter()
    
    expected_year = datetime.now().year - 2
    assert filter.year_from == expected_year
    assert filter.year_to is None
    assert filter.venue is None
    assert filter.issn is None


def test_search_filter_custom():
    """Test custom filter values."""
    filter = SearchFilter(
        year_from=2020,
        year_to=2024,
        venue="Nature",
        issn="0028-0836",
    )
    
    assert filter.year_from == 2020
    assert filter.year_to == 2024
    assert filter.venue == "Nature"
    assert filter.issn == "0028-0836"


def test_search_filter_native_params():
    """Test native params passthrough."""
    filter = SearchFilter(native_params={"has-funder": "true"})
    
    assert filter.native_params["has-funder"] == "true"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/models/test_search_filter.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'libby.models.search_filter'"

- [ ] **Step 3: Write minimal implementation**

```python
# libby/models/search_filter.py
"""Unified search filter model."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchFilter:
    """Unified search filter, each API client converts to native params.
    
    Provides:
    - Time range filtering (year_from, year_to)
    - Venue filtering (venue name, ISSN)
    - Native params passthrough for advanced users
    
    Each API client implements conversion:
    - Crossref: filter=from-pub-date:{year},issn:{issn}
    - Semantic Scholar: year={year}, venue={name}
    - Scholarly: Modify query with "after:{year}", "source:{venue}"
    """
    
    # Time range
    year_from: Optional[int] = None  # Default: current year - 2
    year_to: Optional[int] = None
    
    # Venue
    venue: Optional[str] = None  # Journal/conference name
    issn: Optional[str] = None   # ISSN for precise matching
    
    # Native params (passthrough for advanced users)
    native_params: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default year_from to 2 years ago."""
        if self.year_from is None:
            from datetime import datetime
            self.year_from = datetime.now().year - 2
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/models/test_search_filter.py -v
```

Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add libby/models/search_filter.py tests/models/test_search_filter.py
git commit -m "feat: SearchFilter unified model for multi-API filter translation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: SearchResult Model

**Files:**
- Create: `libby/models/search_result.py`
- Create: `tests/models/test_search_result.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/models/test_search_result.py
"""Tests for SearchResult model."""

from libby.models.search_result import SearchResult, SerpapiExtraInfo


def test_search_result_merge():
    """Test field merging - longer values and missing fields."""
    r1 = SearchResult(
        doi="10.1234/test",
        title="Test Paper",
        author=["Smith, John"],
        sources=["crossref"],
    )
    
    r2 = SearchResult(
        doi="10.1234/test",
        title="Test Paper: A Longer Title",
        journal="Nature",
        sources=["semantic_scholar"],
    )
    
    r1.merge_from(r2)
    
    assert r1.title == "Test Paper: A Longer Title"  # Longer title kept
    assert r1.journal == "Nature"  # Missing field filled
    assert "crossref" in r1.sources
    assert "semantic_scholar" in r1.sources


def test_search_result_to_dict():
    """Test serialization."""
    r = SearchResult(
        doi="10.1234/test",
        title="Test",
        year=2023,
        sources=["crossref"],
    )
    
    d = r.to_dict()
    
    assert d["doi"] == "10.1234/test"
    assert d["title"] == "Test"
    assert d["year"] == 2023
    assert d["sources"] == ["crossref"]


def test_serpapi_extra_info():
    """Test Serpapi extra info."""
    e = SerpapiExtraInfo(
        doi="10.1234/test",
        link="https://example.com",
        cited_by_count=42,
    )
    
    d = e.to_dict()
    
    assert d["doi"] == "10.1234/test"
    assert d["cited_by_count"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/models/test_search_result.py -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# libby/models/search_result.py
"""Search result models with multi-source field merging."""

from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class SearchResult:
    """Single search result, supports field merging from multiple sources."""
    
    doi: Optional[str] = None
    title: Optional[str] = None
    author: list[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    abstract: Optional[str] = None
    
    # Source tracking
    sources: list[str] = field(default_factory=list)
    
    # BibTeX fields
    entry_type: str = "article"
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    
    def merge_from(self, other: "SearchResult") -> "SearchResult":
        """Merge another result, fill missing fields.
        
        Strategy:
        - If self field is empty, fill from other
        - Keep longer value if both have same field
        - Combine sources list
        """
        if not self.doi and other.doi:
            self.doi = other.doi
        
        # Title: keep longer
        if not self.title and other.title:
            self.title = other.title
        elif self.title and other.title and len(other.title) > len(self.title):
            self.title = other.title
        
        # Author: fill if empty
        if not self.author and other.author:
            self.author = other.author
        
        # Year: fill if empty
        if not self.year and other.year:
            self.year = other.year
        
        # Journal: keep longer
        if not self.journal and other.journal:
            self.journal = other.journal
        elif self.journal and other.journal and len(other.journal) > len(self.journal):
            self.journal = other.journal
        
        # Abstract: keep longer
        if not self.abstract and other.abstract:
            self.abstract = other.abstract
        elif self.abstract and other.abstract and len(other.abstract) > len(self.abstract):
            self.abstract = other.abstract
        
        # Combine sources (avoid duplicates)
        for src in other.sources:
            if src not in self.sources:
                self.sources.append(src)
        
        # BibTeX fields: fill if empty
        if not self.volume and other.volume:
            self.volume = other.volume
        if not self.number and other.number:
            self.number = other.number
        if not self.pages and other.pages:
            self.pages = other.pages
        if not self.publisher and other.publisher:
            self.publisher = other.publisher
        if not self.url and other.url:
            self.url = other.url
        
        return self
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "doi": self.doi,
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "journal": self.journal,
            "abstract": self.abstract,
            "sources": self.sources,
            "entry_type": self.entry_type,
            "volume": self.volume,
            "number": self.number,
            "pages": self.pages,
            "publisher": self.publisher,
            "url": self.url,
        }


@dataclass
class SerpapiExtraInfo:
    """Serpapi extra info, stored separately.
    
    Contains link information for user follow-up actions.
    """
    
    doi: Optional[str] = None
    link: Optional[str] = None
    pdf_link: Optional[str] = None
    cited_by_count: Optional[int] = None
    related_articles_link: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "link": self.link,
            "pdf_link": self.pdf_link,
            "cited_by_count": self.cited_by_count,
            "related_articles_link": self.related_articles_link,
        }


@dataclass
class SearchResults:
    """Batch search results."""
    
    query: str
    results: list[SearchResult]
    serpapi_extra: list[SerpapiExtraInfo] = field(default_factory=list)
    total_count: int = 0
    sources_used: list[str] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Output JSON format."""
        data = {
            "query": self.query,
            "total_count": self.total_count,
            "sources_used": self.sources_used,
            "results": [r.to_dict() for r in self.results],
            "serpapi_extra": [e.to_dict() for e in self.serpapi_extra],
        }
        return json.dumps(data, indent=2)
    
    def to_bibtex(self, citekey_config) -> str:
        """Output BibTeX format using existing citekey logic."""
        from libby.core.citekey import CitekeyFormatter
        from libby.models.metadata import BibTeXMetadata
        from libby.output.bibtex import BibTeXFormatter
        
        formatter = BibTeXFormatter()
        citekey_gen = CitekeyFormatter(citekey_config)
        
        bibtex_entries = []
        for r in self.results:
            if r.doi:  # Only output entries with DOI
                metadata = BibTeXMetadata(
                    citekey=citekey_gen.format(r),
                    entry_type=r.entry_type,
                    author=r.author,
                    title=r.title or "",
                    year=r.year,
                    doi=r.doi,
                    journal=r.journal,
                    volume=r.volume,
                    number=r.number,
                    pages=r.pages,
                    publisher=r.publisher,
                    url=r.url,
                )
                bibtex_entries.append(formatter.format(metadata))
        
        return "\n".join(bibtex_entries)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/models/test_search_result.py -v
```

Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add libby/models/search_result.py tests/models/test_search_result.py
git commit -m "feat: SearchResult model with multi-source field merging

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Crossref Search Extension

**Files:**
- Modify: `libby/api/crossref.py`
- Modify: `tests/api/test_crossref.py` (add tests)

- [ ] **Step 1: Read existing crossref.py**

```bash
Read libby/api/crossref.py to understand existing structure.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/api/test_crossref.py (append new tests)

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.crossref import CrossrefAPI
from libby.models.search_filter import SearchFilter


@pytest.mark.asyncio
async def test_search_with_filter():
    """Test search with SearchFilter."""
    api = CrossrefAPI(mailto="test@example.com")
    
    mock_response = {
        "status": "ok",
        "message": {
            "items": [
                {"DOI": "10.1234/test1", "title": ["Test Paper 1"]},
                {"DOI": "10.1234/test2", "title": ["Test Paper 2"]},
            ]
        }
    }
    
    filter = SearchFilter(year_from=2020, year_to=2024)
    
    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        results = await api.search("machine learning", filter=filter)
        
        assert len(results) == 2
        call_params = mock_get.call_args.kwargs.get("params", {})
        assert "from-pub-date:2020" in call_params.get("filter", "")
    
    await api.close()


@pytest.mark.asyncio
async def test_search_with_issn():
    """Test search with ISSN filter."""
    api = CrossrefAPI()
    
    filter = SearchFilter(issn="0028-0836")
    
    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"status": "ok", "message": {"items": []}}
        
        await api.search("test", filter=filter)
        
        call_params = mock_get.call_args.kwargs.get("params", {})
        assert "issn:0028-0836" in call_params.get("filter", "")
    
    await api.close()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/api/test_crossref.py -v -k search
```

Expected: FAIL with "AttributeError: 'CrossrefAPI' object has no attribute 'search'"

- [ ] **Step 4: Write minimal implementation**

Add to `libby/api/crossref.py`:

```python
# Add import at top
from libby.models.search_filter import SearchFilter

# Add method to CrossrefAPI class
async def search(
    self,
    query: str,
    rows: int = 50,
    filter: SearchFilter | None = None,
) -> list[dict]:
    """Search papers, convert SearchFilter to Crossref native params.
    
    Crossref filter syntax:
        from-pub-date:{year}
        until-pub-date:{year}
        issn:{issn}
    
    Args:
        query: Search keywords
        rows: Result count (default 50)
        filter: Unified SearchFilter
    
    Returns:
        Raw result list from Crossref
    """
    url = f"{self.BASE_URL}/works"
    params = {
        "query.bibliographic": query,
        "rows": rows,
    }
    
    if filter is None:
        filter = SearchFilter()
    
    filters = []
    
    # Year range
    filters.append(f"from-pub-date:{filter.year_from}")
    if filter.year_to:
        filters.append(f"until-pub-date:{filter.year_to}")
    
    # ISSN
    if filter.issn:
        filters.append(f"issn:{filter.issn}")
    
    # Native params passthrough
    for k, v in filter.native_params.items():
        filters.append(f"{k}:{v}")
    
    params["filter"] = ",".join(filters)
    
    if self.mailto:
        params["mailto"] = self.mailto
    
    data = await self.get(url, params=params)
    if data.get("status") == "ok":
        return data.get("message", {}).get("items", [])
    return []
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/api/test_crossref.py -v -k search
```

Expected: 2/2 PASS

- [ ] **Step 6: Commit**

```bash
git add libby/api/crossref.py tests/api/test_crossref.py
git commit -m "feat: Crossref search() with SearchFilter translation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Semantic Scholar Search Extension

**Files:**
- Modify: `libby/api/semantic_scholar.py`
- Modify: `tests/api/test_semantic_scholar.py` (add tests)

- [ ] **Step 1: Read existing semantic_scholar.py**

```bash
Read libby/api/semantic_scholar.py to understand existing structure.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/api/test_semantic_scholar.py (append new tests)

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.models.search_filter import SearchFilter


@pytest.mark.asyncio
async def test_search_with_year_filter():
    """Test search with year range filter."""
    api = SemanticScholarAPI(api_key="test-key")
    
    mock_response = {
        "data": [
            {"title": "Test Paper", "year": 2023, "authors": [{"name": "Smith"}]},
        ]
    }
    
    filter = SearchFilter(year_from=2020, year_to=2024)
    
    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        results = await api.search("AI", filter=filter)
        
        assert len(results) == 1
        call_params = mock_get.call_args.kwargs.get("params", {})
        assert call_params["year"] == "2020-2024"
    
    await api.close()


@pytest.mark.asyncio
async def test_search_with_venue_filter():
    """Test search with venue filter."""
    api = SemanticScholarAPI()
    
    filter = SearchFilter(venue="Nature")
    
    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"data": []}
        
        await api.search("test", filter=filter)
        
        call_params = mock_get.call_args.kwargs.get("params", {})
        assert call_params["venue"] == "Nature"
    
    await api.close()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/api/test_semantic_scholar.py -v -k search
```

Expected: FAIL with "AttributeError: 'SemanticScholarAPI' object has no attribute 'search'"

- [ ] **Step 4: Write minimal implementation**

Add to `libby/api/semantic_scholar.py`:

```python
# Add import at top
from libby.models.search_filter import SearchFilter

# Add method to SemanticScholarAPI class
async def search(
    self,
    query: str,
    limit: int = 50,
    filter: SearchFilter | None = None,
) -> list[dict]:
    """Search papers, convert SearchFilter to S2 native params.
    
    Semantic Scholar params:
        year={year} or year={from}-{to}
        venue={venue_name}
    
    Args:
        query: Search keywords
        limit: Result count
        filter: Unified SearchFilter
    
    Returns:
        Raw result list from S2
    """
    url = f"{self.BASE_URL}/paper/search"
    
    if filter is None:
        filter = SearchFilter()
    
    # Year range
    year_param = str(filter.year_from)
    if filter.year_to:
        year_param = f"{filter.year_from}-{filter.year_to}"
    
    params = {
        "query": query,
        "limit": limit,
        "year": year_param,
        "fields": "title,year,authors,abstract,externalIds,venue,journal,issn",
    }
    
    # Venue filter
    if filter.venue:
        params["venue"] = filter.venue
    
    headers = {}
    if self.api_key:
        headers["x-api-key"] = self.api_key
    
    data = await self.get(url, params=params, headers=headers)
    
    if data and "data" in data:
        return data["data"]
    return []
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/api/test_semantic_scholar.py -v -k search
```

Expected: 2/2 PASS

- [ ] **Step 6: Commit**

```bash
git add libby/api/semantic_scholar.py tests/api/test_semantic_scholar.py
git commit -m "feat: Semantic Scholar search() with SearchFilter translation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Scholarly Wrapper

**Files:**
- Create: `libby/api/scholarly.py`
- Create: `tests/api/test_scholarly.py`

**Note:** `scholarly` is already in pyproject.toml dependencies.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_scholarly.py
"""Tests for Scholarly wrapper."""

import pytest
from unittest.mock import patch
from libby.api.scholarly import ScholarlyAPI
from libby.models.search_filter import SearchFilter


@pytest.mark.asyncio
async def test_search_basic():
    """Test basic search returns results."""
    api = ScholarlyAPI()
    
    mock_results = [
        {"bib": {"title": "Test Paper 1"}},
        {"bib": {"title": "Test Paper 2"}},
    ]
    
    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter(mock_results)
        
        results = await api.search("machine learning", limit=2)
        
        assert len(results) == 2


@pytest.mark.asyncio
async def test_search_with_year_filter():
    """Test year filter adds keywords to query."""
    api = ScholarlyAPI()
    
    filter = SearchFilter(year_from=2020, year_to=2024)
    
    with patch('libby.api.scholarly.scholarly.search_pubs') as mock_search:
        mock_search.return_value = iter([])
        
        await api.search("AI", filter=filter)
        
        # Verify query was enhanced with year keywords
        call_args = mock_search.call_args[0]
        assert "after:2020" in call_args[0]
        assert "before:2024" in call_args[0]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/api/test_scholarly.py -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# libby/api/scholarly.py
"""Google Scholar search wrapper using scholarly package."""

import asyncio
from typing import Optional

from scholarly import scholarly
from libby.models.search_filter import SearchFilter


class ScholarlyAPI:
    """Google Scholar search via scholarly package.
    
    Note: scholarly is a sync library, wrapped in async executor.
    May trigger Google anti-bot, use conservative rate limit.
    """
    
    async def search(
        self,
        query: str,
        limit: int = 50,
        filter: SearchFilter | None = None,
    ) -> list[dict]:
        """Search Google Scholar.
        
        Converts SearchFilter to query keywords:
        - year_from/year_to: "after:{year}", "before:{year}"
        - venue: "source:{venue}"
        
        Args:
            query: Search keywords
            limit: Result count
            filter: Unified SearchFilter
        
        Returns:
            Raw result list from scholarly
        """
        if filter is None:
            filter = SearchFilter()
        
        # Enhance query with filter keywords
        enhanced_query = query
        
        if filter.year_from:
            enhanced_query += f" after:{filter.year_from}"
        if filter.year_to:
            enhanced_query += f" before:{filter.year_to}"
        if filter.venue:
            enhanced_query += f" source:{filter.venue}"
        
        def _sync_search():
            """Sync search in thread."""
            results = []
            try:
                search_gen = scholarly.search_pubs(enhanced_query)
                for i, result in enumerate(search_gen):
                    if i >= limit:
                        break
                    results.append(result)
            except Exception:
                # Handle anti-bot or network errors gracefully
                pass
            return results
        
        # Run in thread pool (scholarly is sync)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_search)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/api/test_scholarly.py -v
```

Expected: 2/2 PASS

- [ ] **Step 5: Commit**

```bash
git add libby/api/scholarly.py tests/api/test_scholarly.py
git commit -m "feat: Scholarly wrapper for Google Scholar search

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Serpapi Search Extension

**Files:**
- Modify: `libby/api/serpapi.py`
- Modify: `tests/api/test_serpapi.py` (add tests)

- [ ] **Step 1: Read existing serpapi.py**

```bash
Read libby/api/serpapi.py to understand existing structure.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/api/test_serpapi.py (append new tests)

import pytest
from unittest.mock import AsyncMock, patch
from libby.api.serpapi import SerpapiAPI


@pytest.mark.asyncio
async def test_search_quota_reached():
    """Test quota detection returns (results, True)."""
    api = SerpapiAPI()
    
    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"error": "Invalid API key"}
        
        results, quota_reached = await api.search("test", "bad-key")
        
        assert quota_reached is True


@pytest.mark.asyncio
async def test_search_pagination():
    """Test multi-page search (2 pages)."""
    api = SerpapiAPI()
    
    mock_page1 = {"organic_results": [{"title": "Paper 1"}]}
    mock_page2 = {"organic_results": [{"title": "Paper 2"}]}
    
    with patch.object(api, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_page1, mock_page2]
        
        results, quota_reached = await api.search("test", "key", max_pages=2)
        
        assert len(results) == 2
        assert quota_reached is False
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/api/test_serpapi.py -v -k search
```

Expected: FAIL with "AttributeError"

- [ ] **Step 4: Write minimal implementation**

Add to `libby/api/serpapi.py`:

```python
# Add method to SerpapiAPI class
async def search(
    self,
    query: str,
    api_key: str,
    max_pages: int = 5,
) -> tuple[list[dict], bool]:
    """Search Google Scholar via Serpapi.
    
    Controlled API usage:
    - Max 5 pages per search (50 results)
    - Retry on failure (max 2 per page)
    
    Args:
        query: Search keywords
        api_key: Serpapi API key
        max_pages: Max pages to fetch
    
    Returns:
        (results, quota_reached)
        quota_reached=True means skip Serpapi
    """
    all_results = []
    
    for page in range(max_pages):
        # Retry logic (2 retries per page)
        for retry in range(2):
            try:
                params = {
                    "engine": "google_scholar",
                    "q": query,
                    "api_key": api_key,
                    "start": page * 10,
                    "num": 10,
                }
                
                data = await self.get(self.BASE_URL, params=params)
                
                if not data or "error" in data:
                    error = data.get("error", "") if data else ""
                    if "quota" in error.lower() or "Invalid API key" in error:
                        return all_results, True  # Quota reached
                    
                    if retry < 1:
                        continue  # Retry
                    else:
                        break  # Give up on this page
                
                organic = data.get("organic_results", [])
                all_results.extend(organic)
                break  # Success, move to next page
                
            except Exception:
                if retry < 1:
                    continue
                else:
                    break
    
    return all_results, False
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/api/test_serpapi.py -v -k search
```

Expected: 2/2 PASS

- [ ] **Step 6: Commit**

```bash
git add libby/api/serpapi.py tests/api/test_serpapi.py
git commit -m "feat: Serpapi search() with pagination and quota control

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: WebSearcher Core

**Files:**
- Create: `libby/core/websearch.py`
- Create: `tests/core/test_websearch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_websearch.py
"""Tests for WebSearcher."""

import pytest
from unittest.mock import AsyncMock, patch
from libby.models.config import LibbyConfig
from libby.core.websearch import WebSearcher


@pytest.fixture
def config():
    return LibbyConfig()


@pytest.fixture
def searcher(config):
    return WebSearcher(config)


@pytest.mark.asyncio
async def test_search_parallel_execution(searcher):
    """Test parallel search across multiple sources."""
    with patch.object(searcher.crossref, 'search', new_callable=AsyncMock) as m1:
        m1.return_value = [{"DOI": "10.1", "title": ["Test 1"]}]
        
        with patch.object(searcher.s2, 'search', new_callable=AsyncMock) as m2:
            m2.return_value = [{"externalIds": {"DOI": "10.2"}, "title": "Test 2"}]
            
            with patch.object(searcher.scholarly, 'search', new_callable=AsyncMock) as m3:
                m3.return_value = [{"bib": {"title": "Test 3"}}]
                
                results = await searcher.search("test", limit=10, skip_serpapi=True)
                
                assert results.total_count >= 1
                assert "crossref" in results.sources_used
                assert "semantic_scholar" in results.sources_used


@pytest.mark.asyncio
async def test_merge_by_doi(searcher):
    """Test DOI merging keeps longer values."""
    from libby.models.search_result import SearchResult
    
    r1 = SearchResult(doi="10.1", title="Short", sources=["crossref"])
    r2 = SearchResult(doi="10.1", title="Longer Title", journal="Nature", sources=["s2"])
    
    merged = searcher._merge_by_doi([r1, r2])
    
    assert len(merged) == 1
    assert merged[0].title == "Longer Title"
    assert merged[0].journal == "Nature"
    assert "crossref" in merged[0].sources
    assert "s2" in merged[0].sources
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/test_websearch.py -v
```

Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# libby/core/websearch.py
"""WebSearcher orchestrates multi-source parallel search."""

import asyncio
import os
from typing import Optional

from rich.console import Console

from libby.models.config import LibbyConfig
from libby.models.search_result import SearchResult, SearchResults, SerpapiExtraInfo
from libby.models.search_filter import SearchFilter
from libby.api.crossref import CrossrefAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.scholarly import ScholarlyAPI
from libby.api.serpapi import SerpapiAPI


class WebSearcher:
    """Orchestrates parallel search across multiple sources."""
    
    def __init__(self, config: LibbyConfig):
        self.config = config
        
        self.crossref = CrossrefAPI(mailto=os.getenv("EMAIL"))
        self.s2 = SemanticScholarAPI(api_key=os.getenv("S2_API_KEY"))
        self.scholarly = ScholarlyAPI()
        self.serpapi = SerpapiAPI() if os.getenv("SERPAPI_API_KEY") else None
    
    async def search(
        self,
        query: str,
        filter: SearchFilter | None = None,
        limit: int = 50,
        skip_serpapi: bool = False,
    ) -> SearchResults:
        """Execute parallel search.
        
        1. Crossref + S2 + Scholarly in parallel
        2. Merge results by DOI
        3. Serpapi separately (controlled usage)
        """
        if filter is None:
            filter = SearchFilter()
        
        # Parallel execution
        results = await asyncio.gather(
            self.crossref.search(query, rows=limit, filter=filter),
            self.s2.search(query, limit=limit, filter=filter),
            self.scholarly.search(query, limit=limit, filter=filter),
            return_exceptions=True,
        )
        
        all_results = []
        sources_used = []
        
        # Parse Crossref
        if not isinstance(results[0], Exception):
            for item in results[0]:
                r = self._parse_crossref(item)
                r.sources.append("crossref")
                all_results.append(r)
            sources_used.append("crossref")
        
        # Parse S2
        if not isinstance(results[1], Exception):
            for item in results[1]:
                r = self._parse_s2(item)
                r.sources.append("semantic_scholar")
                all_results.append(r)
            sources_used.append("semantic_scholar")
        
        # Parse Scholarly
        if not isinstance(results[2], Exception):
            for item in results[2]:
                r = self._parse_scholarly(item)
                r.sources.append("google_scholar")
                all_results.append(r)
            sources_used.append("google_scholar")
        
        # Merge by DOI
        merged = self._merge_by_doi(all_results)
        
        # Serpapi separately
        serpapi_extra = []
        if not skip_serpapi and self.serpapi:
            serpapi_results, quota_reached = await self.serpapi.search(
                query, os.getenv("SERPAPI_API_KEY"), max_pages=5
            )
            
            if quota_reached:
                Console().print("[yellow]Serpapi API quota reached[/yellow]")
            else:
                Console().print("[green]Serpapi search completed (max 5 pages)[/green]")
                
                for item in serpapi_results:
                    doi = self._extract_doi_from_serpapi(item)
                    if doi:
                        existing = next((r for r in merged if r.doi == doi), None)
                        if existing:
                            existing.sources.append("serpapi")
                        else:
                            r = self._parse_serpapi(item)
                            r.sources.append("serpapi")
                            merged.append(r)
                    
                    serpapi_extra.append(SerpapiExtraInfo(
                        doi=doi,
                        link=item.get("link"),
                        pdf_link=self._extract_pdf_link(item),
                        cited_by_count=item.get("cited_by", {}).get("total"),
                    ))
                
                sources_used.append("serpapi")
        
        return SearchResults(
            query=query,
            results=merged[:limit],
            serpapi_extra=serpapi_extra,
            total_count=len(merged),
            sources_used=sources_used,
        )
    
    def _parse_crossref(self, item: dict) -> SearchResult:
        """Parse Crossref result."""
        authors = []
        if "author" in item:
            for a in item["author"]:
                family = a.get("family", "")
                given = a.get("given", "")
                if family:
                    authors.append(f"{family}, {given}" if given else family)
        
        year = None
        pub = item.get("published-print") or item.get("published-online")
        if pub and "date-parts" in pub:
            year = pub["date-parts"][0][0]
        
        return SearchResult(
            doi=item.get("DOI"),
            title=item.get("title", [""])[0] if isinstance(item.get("title"), list) else "",
            author=authors,
            year=year,
            journal=item.get("container-title", [""])[0] if isinstance(item.get("container-title"), list) else "",
            entry_type=item.get("type", "article"),
            volume=item.get("volume"),
            number=item.get("issue"),
            pages=item.get("page"),
            publisher=item.get("publisher"),
            url=item.get("URL"),
        )
    
    def _parse_s2(self, item: dict) -> SearchResult:
        """Parse Semantic Scholar result."""
        authors = []
        if "authors" in item:
            authors = [a.get("name", "") for a in item["authors"]]
        
        ext_ids = item.get("externalIds") or {}
        
        return SearchResult(
            doi=ext_ids.get("DOI"),
            title=item.get("title"),
            author=authors,
            year=item.get("year"),
            journal=item.get("venue") or item.get("journal"),
            abstract=item.get("abstract"),
        )
    
    def _parse_scholarly(self, item: dict) -> SearchResult:
        """Parse Scholarly result."""
        bib = item.get("bib", {})
        
        return SearchResult(
            doi=None,
            title=bib.get("title"),
            author=[bib.get("author", "")] if bib.get("author") else [],
            year=int(bib.get("pub_year")) if bib.get("pub_year") else None,
            journal=bib.get("venue"),
            abstract=bib.get("abstract"),
        )
    
    def _parse_serpapi(self, item: dict) -> SearchResult:
        """Parse Serpapi result."""
        return SearchResult(
            doi=self._extract_doi_from_serpapi(item),
            title=item.get("title"),
            author=[item.get("authors", "")] if item.get("authors") else [],
            journal=item.get("publication_info", {}).get("journal"),
        )
    
    def _extract_doi_from_serpapi(self, item: dict) -> Optional[str]:
        """Extract DOI from Serpapi result."""
        pub_info = item.get("publication_info", {})
        if "doi" in pub_info:
            return pub_info["doi"]
        
        link = item.get("link", "")
        if "doi.org/" in link:
            return link.split("doi.org/")[-1].split("?")[0]
        
        return None
    
    def _extract_pdf_link(self, item: dict) -> Optional[str]:
        """Extract PDF link from Serpapi result."""
        resources = item.get("resources", [])
        for res in resources:
            if res.get("file_format") == "PDF":
                return res.get("link")
        return None
    
    def _merge_by_doi(self, results: list[SearchResult]) -> list[SearchResult]:
        """Merge results by DOI."""
        doi_map = {}
        no_doi = []
        
        for r in results:
            if r.doi:
                if r.doi in doi_map:
                    doi_map[r.doi].merge_from(r)
                else:
                    doi_map[r.doi] = r
            else:
                no_doi.append(r)
        
        return list(doi_map.values()) + no_doi
    
    async def close(self):
        """Close API sessions."""
        await self.crossref.close()
        await self.s2.close()
        if self.serpapi:
            await self.serpapi.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/core/test_websearch.py -v
```

Expected: 2/2 PASS

- [ ] **Step 5: Commit**

```bash
git add libby/core/websearch.py tests/core/test_websearch.py
git commit -m "feat: WebSearcher core orchestrator

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: CLI Websearch Command

**Files:**
- Create: `libby/cli/websearch.py`
- Create: `tests/cli/test_websearch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_websearch.py
"""Tests for websearch CLI command."""

from typer.testing import CliRunner
from libby.__main__ import app

runner = CliRunner()


def test_websearch_help():
    """Test --help shows usage."""
    result = runner.invoke(app, ["websearch", "--help"])
    assert result.exit_code == 0
    assert "Search" in result.stdout


def test_websearch_no_query():
    """Test missing query shows error."""
    result = runner.invoke(app, ["websearch", "--no-env-check"])
    assert result.exit_code == 1
    assert "No query" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/cli/test_websearch.py -v
```

Expected: FAIL with "No such command 'websearch'"

- [ ] **Step 3: Write minimal implementation**

```python
# libby/cli/websearch.py
"""libby websearch command."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from libby.config.loader import load_config
from libby.config.env_check import check_env_vars
from libby.core.websearch import WebSearcher
from libby.core.pdf_fetcher import PDFFetcher
from libby.core.metadata import MetadataExtractor
from libby.models.search_filter import SearchFilter
from libby.output.bibtex import BibTeXFormatter
from libby.utils.doi_parser import is_doi

console = Console()


def websearch(
    query: str = typer.Argument(None, help="Search keywords or DOI"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    format: str = typer.Option("bibtex", "--format", "-f", help="bibtex or json"),
    limit: int = typer.Option(50, "--limit", "-l", help="Results per source"),
    year_from: Optional[int] = typer.Option(None, "--year-from", help="Start year"),
    year_to: Optional[int] = typer.Option(None, "--year-to", help="End year"),
    venue: Optional[str] = typer.Option(None, "--venue", help="Journal/conference"),
    issn: Optional[str] = typer.Option(None, "--issn", help="ISSN"),
    no_serpapi: bool = typer.Option(False, "--no-serpapi", help="Skip Serpapi"),
    config_path: Optional[Path] = typer.Option(None, "--config"),
    no_env_check: bool = typer.Option(False, "--no-env-check"),
):
    """Search academic databases.
    
    DOI input triggers fetch -> extract fallback.
    
    Examples:
        libby websearch "machine learning"
        libby websearch 10.1234/test
        libby websearch "AI" --year-from 2020 --venue Nature
    """
    if not no_env_check:
        check_env_vars()
    
    config = load_config(config_path)
    
    # Gather input
    if not query:
        from libby.cli.utils import read_stdin_lines
        stdin = read_stdin_lines()
        if stdin:
            query = stdin[0]
        else:
            console.print("[red]No query provided[/red]")
            raise typer.Exit(1)
    
    # DOI fallback
    if is_doi(query):
        console.print("[yellow]DOI detected -> fetch/extract[/yellow]")
        _handle_doi(query, config)
        return
    
    # Build filter
    filter = SearchFilter(
        year_from=year_from,
        year_to=year_to,
        venue=venue,
        issn=issn,
    )
    
    # Execute search
    async def run():
        searcher = WebSearcher(config)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Searching...", total=None)
            results = await searcher.search(query, filter, limit, no_serpapi)
            progress.remove_task(task)
        
        await searcher.close()
        return results
    
    results = asyncio.run(run())
    
    # Display table
    _display_table(results, console)
    
    # Output
    if format == "json":
        output_text = results.to_json()
    else:
        output_text = results.to_bibtex(config.citekey)
    
    if output:
        output.write_text(output_text)
        console.print(f"[green]Saved: {output}[/green]")
        
        if results.serpapi_extra:
            serpapi_file = output.parent / f"{output.stem}_serpapi.json"
            serpapi_file.write_text(json.dumps(
                [e.to_dict() for e in results.serpapi_extra], indent=2
            ))
            console.print(f"[green]Serpapi extra: {serpapi_file}[/green]")
    else:
        console.print(output_text)
    
    console.print(f"\n[green]Total: {results.total_count}[/green]")
    console.print(f"[blue]Sources: {', '.join(results.sources_used)}[/blue]")


def _handle_doi(doi: str, config):
    """DOI -> fetch -> extract fallback."""
    async def run():
        extractor = MetadataExtractor(config)
        fetcher = PDFFetcher(config)
        
        try:
            console.print(f"[green]Fetching PDF: {doi}[/green]")
            result = await fetcher.fetch(doi)
            
            if result.success:
                target_dir = config.papers_dir / "temp"
                target_dir.mkdir(parents=True, exist_ok=True)
                target_pdf = target_dir / f"{doi.replace('/', '_')}.pdf"
                
                success = await fetcher.download_pdf_to_file(result.pdf_url, target_pdf)
                
                if success:
                    metadata = await extractor.extract_from_doi(doi)
                    console.print(BibTeXFormatter().format(metadata))
                    console.print(f"[green]PDF: {target_pdf}[/green]")
                else:
                    console.print("[yellow]PDF download failed[/yellow]")
                    metadata = await extractor.extract_from_doi(doi)
                    console.print(BibTeXFormatter().format(metadata))
            else:
                console.print("[yellow]No PDF found[/yellow]")
                metadata = await extractor.extract_from_doi(doi)
                console.print(BibTeXFormatter().format(metadata))
        finally:
            await extractor.close()
            await fetcher.close()
    
    asyncio.run(run())


def _display_table(results, console):
    """Display results table."""
    table = Table(title="Search Results")
    
    table.add_column("#", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Author", style="blue")
    table.add_column("Year", style="yellow")
    table.add_column("Journal", style="magenta")
    table.add_column("DOI", style="cyan")
    
    for i, r in enumerate(results.results[:20], 1):
        table.add_row(
            str(i),
            (r.title[:40] + "...") if r.title and len(r.title) > 40 else r.title or "",
            r.author[0] if r.author else "",
            str(r.year) if r.year else "",
            (r.journal[:25] + "...") if r.journal and len(r.journal) > 25 else r.journal or "",
            r.doi or "",
        )
    
    console.print(table)
```

- [ ] **Step 4: Register in __main__.py**

Add to `libby/__main__.py`:

```python
# Add after existing command registrations
from libby.cli.websearch import websearch
app.command(name="websearch")(websearch)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/cli/test_websearch.py -v
```

Expected: 2/2 PASS

- [ ] **Step 6: Commit**

```bash
git add libby/cli/websearch.py libby/__main__.py tests/cli/test_websearch.py
git commit -m "feat: libby websearch CLI command

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Manual CLI Test

- [ ] **Step 1: Test CLI integration**

```bash
uv run libby websearch --help
```

Expected: Shows help with all options

- [ ] **Step 2: Test basic search**

```bash
uv run libby websearch "machine learning" --limit 10 --no-serpapi --no-env-check
```

Expected: Shows search results table

---

### Task 10: Integration Tests

**Files:**
- Create: `tests/integration/test_websearch.py`

- [ ] **Step 1: Create integration tests**

```python
# tests/integration/test_websearch.py
"""Integration tests for websearch."""

import pytest
from libby.models.config import LibbyConfig
from libby.core.websearch import WebSearcher
from libby.models.search_filter import SearchFilter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websearch_real_query():
    """Test real search query (requires network)."""
    config = LibbyConfig()
    searcher = WebSearcher(config)
    
    results = await searcher.search(
        "machine learning",
        limit=10,
        skip_serpapi=True,
    )
    
    assert results.total_count > 0
    assert len(results.sources_used) >= 1
    
    await searcher.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websearch_with_year_filter():
    """Test search with year filter."""
    config = LibbyConfig()
    searcher = WebSearcher(config)
    
    filter = SearchFilter(year_from=2023)
    
    results = await searcher.search(
        "artificial intelligence",
        filter=filter,
        limit=10,
        skip_serpapi=True,
    )
    
    for r in results.results:
        if r.year:
            assert r.year >= 2023
    
    await searcher.close()
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/integration/test_websearch.py -v -m integration
```

Expected: 2/2 PASS (requires network)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_websearch.py
git commit -m "test: websearch integration tests

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 11: Documentation Updates

- [ ] **Step 1: Update README.md**

Add websearch usage section to `README.md`.

- [ ] **Step 2: Update CHANGELOG.md**

Document websearch feature.

- [ ] **Step 3: Update CLAUDE.md**

Update websearch section with actual implementation details.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md CLAUDE.md
git commit -m "docs: update documentation for websearch

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Plan Self-Review

**1. Spec coverage:**

| Spec Requirement | Task |
|-----------------|------|
| SearchFilter model | Task 1 ✅ |
| SearchResult model | Task 2 ✅ |
| Crossref search extension | Task 3 ✅ |
| Semantic Scholar search extension | Task 4 ✅ |
| Scholarly wrapper | Task 5 ✅ |
| Serpapi search (5 pages, quota) | Task 6 ✅ |
| WebSearcher parallel execution | Task 7 ✅ |
| CLI command | Task 8 ✅ |
| CLI registration | Task 9 ✅ |
| Integration tests | Task 10 ✅ |
| Documentation | Task 11 ✅ |

**2. Placeholder scan:**

✅ No TBD, TODO, or incomplete sections.

**3. Type consistency:**

- SearchFilter used consistently across all API search methods
- SearchResult.merge_from() signature matches usage
- WebSearcher._parse_* methods return SearchResult

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-12-libby-websearch-plan.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**