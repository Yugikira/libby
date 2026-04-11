"""API clients for external services."""

from libby.api.base import AsyncAPIClient, RateLimit
from libby.api.crossref import CrossrefAPI
from libby.api.unpaywall import UnpaywallAPI
from libby.api.semantic_scholar import SemanticScholarAPI
from libby.api.arxiv import ArxivAPI
from libby.api.pmc import PMCAPI
from libby.api.biorxiv import BiorxivAPI
from libby.api.scihub import ScihubAPI
from libby.api.serpapi import SerpapiAPI, SerpapiConfirmationNeeded

__all__ = [
    "AsyncAPIClient",
    "RateLimit",
    "CrossrefAPI",
    "UnpaywallAPI",
    "SemanticScholarAPI",
    "ArxivAPI",
    "PMCAPI",
    "BiorxivAPI",
    "ScihubAPI",
    "SerpapiAPI",
    "SerpapiConfirmationNeeded",
]