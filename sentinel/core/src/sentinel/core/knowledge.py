import httpx
from pydantic import TypeAdapter
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.core.observability.audit import AuditLog

RESULTS = TypeAdapter(list[RetrievedContext])


class KnowledgeClient:
    def __init__(self, endpoint: str):
        self.client = httpx.Client(base_url=endpoint, timeout=30)

    def search(self, request: KnowledgeSearchRequest) -> list[RetrievedContext]:
        body = request.model_dump(mode="json")
        response = self.client.post("/internal/knowledge/search", json=body)
        response.raise_for_status()
        payload = response.json()
        return RESULTS.validate_python(payload)

    def search_text(self, request: KnowledgeSearchRequest, audit: AuditLog) -> str:
        try:
            results = self.search(request)
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            audit.record("knowledge_search_failed", {"error": error_type})
            return "Knowledge search is unavailable; continue with current repository and live evidence."
        excerpts = [f"Source: {item.source}\nScore: {item.score:.3f}\n{item.content}" for item in results]
        return "\n\n".join(excerpts) or "No matching knowledge found."

    def close(self) -> None:
        self.client.close()
