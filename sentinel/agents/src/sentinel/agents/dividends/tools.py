from dataclasses import dataclass
from typing import Protocol

import httpx
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, ToolException, tool
from pydantic import BaseModel, Field
from sentinel.agents.dividends.contracts import SearchResult
from sentinel.agents.dividends.excerpt import focus_text
from sentinel.agents.dividends.settings import ExcerptConfig
from sentinel.agents.framework.runner import RunContext


class WebSearch(Protocol):
    def search(self, query: str) -> list[SearchResult]: ...


class PageSource(Protocol):
    def read(self, url: str) -> str: ...


@dataclass(frozen=True)
class ResearchSources:
    search: WebSearch
    reader: PageSource


@dataclass(frozen=True)
class ToolContext(RunContext):
    sources: ResearchSources
    excerpt: ExcerptConfig


class SearchArguments(BaseModel):
    query: str = Field(description="Web search query, for example the company name, dividend, and year.")


@tool(args_schema=SearchArguments)
def web_search(query: str, runtime: ToolRuntime[ToolContext]) -> str:
    """Search the web and return result titles, URLs, and snippets."""
    try:
        results = runtime.context.sources.search.search(query)
    except (httpx.HTTPError, ValueError) as error:
        raise ToolException(f"search failed: {error}") from error
    if not results:
        return "No results."
    lines = [f"{item.title}\n{item.url}\n{item.snippet}" for item in results]
    return "\n\n".join(lines)


class FetchArguments(BaseModel):
    url: str = Field(description="URL of a page or PDF to read.")


@tool(args_schema=FetchArguments)
def fetch_page(url: str, runtime: ToolRuntime[ToolContext]) -> str:
    """Read a page or PDF and return the passages around dividend terms."""
    context = runtime.context
    try:
        text = context.sources.reader.read(url)
    except (httpx.HTTPError, ValueError) as error:
        raise ToolException(f"page could not be read: {error}") from error
    excerpt = context.excerpt
    return focus_text(text, excerpt.focus_terms, excerpt.window_chars, excerpt.max_chars)


TOOLS: dict[str, BaseTool] = {
    "web_search": web_search,
    "fetch_page": fetch_page,
}
