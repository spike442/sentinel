from sentinel.agents.dividends.contracts import SearchResult
from stonks.core.http import HttpSource
from stonks.dividends.config.settings import SearchConfig


def search_results(response: dict, limit: int) -> list[SearchResult]:
    items = response.get("results") or []
    results = [
        SearchResult(title=item.get("title") or "", url=item["url"], snippet=item.get("content") or "")
        for item in items
        if item.get("url")
    ]
    return results[:limit]


class SearxngSearch:
    def __init__(self, source: HttpSource, search: SearchConfig):
        self.source = source
        self.search_config = search

    def search(self, query: str) -> list[SearchResult]:
        params = {"q": query, "format": "json"}
        response = self.source.get(self.search_config.url, params)
        body = response.json()
        return search_results(body, self.search_config.max_results)
