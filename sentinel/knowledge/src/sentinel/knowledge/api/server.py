from threading import Event

from fastapi import FastAPI, HTTPException
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.knowledge.clickhouse import ClickHouse
from sentinel.knowledge.rag.retriever import RagRetriever


def create_app(retriever: RagRetriever, clickhouse: ClickHouse, indexing_ready: Event) -> FastAPI:
    app = FastAPI(title="Sentinel internal knowledge search", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, str]:
        if not indexing_ready.is_set():
            raise HTTPException(status_code=503, detail="Knowledge indexing unavailable")
        clickhouse.query("SELECT 1")
        return {"status": "ready"}

    @app.post("/internal/knowledge/search", response_model=list[RetrievedContext])
    def search(request: KnowledgeSearchRequest) -> list[RetrievedContext]:
        return retriever.retrieve_context(request.domain.value, request.repository, request.query)

    return app
