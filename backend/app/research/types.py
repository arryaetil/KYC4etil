"""Gedeelde, provider-onafhankelijke researchtypes."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str
    query: str


@dataclass
class CombinedSearchResult:
    title: str
    url: str
    canonical_url: str
    snippets: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlannedQuery:
    pad: str
    query: str
    doel: str
