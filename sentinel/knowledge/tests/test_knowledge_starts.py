import asyncio
from unittest.mock import AsyncMock, Mock


def test_knowledge_service_starts_serving_and_indexing(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_CLICKHOUSE_PASSWORD", "test")
    monkeypatch.setenv("SENTINEL_KNOWLEDGE_DATABASE_PASSWORD", "test")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("SENTINEL_RAG__EMBEDDING_REVISION", "test")
    from sentinel.knowledge.api import main

    server = Mock(serve=AsyncMock())
    indexer = Mock(index_documents=Mock(return_value=0))
    for name in ("ClickHouse", "Embeddings", "RagRetriever"):
        monkeypatch.setattr(main, name, Mock())
    monkeypatch.setattr(main, "RagIndexer", Mock(return_value=indexer))
    monkeypatch.setattr(main, "Server", Mock(return_value=server))

    asyncio.run(main.serve_knowledge())

    server.serve.assert_awaited_once()
    indexer.index_documents.assert_called()
