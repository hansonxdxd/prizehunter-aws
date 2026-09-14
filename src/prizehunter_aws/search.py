"""Discovery seam: no paid provider is enabled in round one."""

from datetime import UTC, datetime
from typing import Protocol

from .contracts import SearchResult


class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 3) -> SearchResult: ...


class UnavailableSearch:
    def search(self, query: str, limit: int = 3) -> SearchResult:
        return SearchResult(
            query=query,
            provider="none",
            status="unavailable",
            reason="No live search provider authorized/configured; this does not mean no opportunities or rules exist.",
            observed_at=datetime.now(UTC),
        )


class ReplaySearch:
    """Exact-query fixtures only, never a fixed list posing as global discovery."""

    def __init__(self, results: dict[str, SearchResult]):
        self.results = results

    def search(self, query: str, limit: int = 3) -> SearchResult:
        if query not in self.results:
            return UnavailableSearch().search(query, limit)
        result = self.results[query]
        return result.model_copy(update={"status": "replay", "candidates": result.candidates[:limit]})
