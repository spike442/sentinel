import asyncio
import logging
import threading

from sentinel.core.observability.logging import configure_logging
from sentinel.knowledge.api.server import create_app
from sentinel.knowledge.clickhouse import ClickHouse
from sentinel.knowledge.config import KnowledgeSettings
from sentinel.knowledge.rag.embeddings import Embeddings
from sentinel.knowledge.rag.indexer import RagIndexer
from sentinel.knowledge.rag.retriever import RagRetriever
from uvicorn import Config, Server

logger = logging.getLogger(__name__)

SEARCH_PORT = 9092


def index_periodically(indexer: RagIndexer, interval: int, stopped: threading.Event, ready: threading.Event) -> None:
    """Index on startup and periodically, retrying a failed pass within a minute.

    The service becomes ready after its first successful pass and stays ready: a later failed pass keeps
    serving the index it already has.
    """
    while not stopped.is_set():
        delay = interval
        try:
            count = indexer.index_documents()
            ready.set()
            logger.info("Knowledge indexing complete changed_documents=%s", count)
        except Exception:
            delay = min(interval, 60)
            logger.exception("Knowledge indexing failed")
        stopped.wait(delay)


async def serve_knowledge() -> None:
    settings = KnowledgeSettings()
    configure_logging(settings.logging.level)
    clickhouse = ClickHouse(settings.clickhouse, settings.clickhouse_password)
    embeddings = Embeddings(settings.rag)
    retriever = RagRetriever(settings, clickhouse, embeddings)
    stopped = threading.Event()
    ready = threading.Event()
    indexer = RagIndexer(settings, clickhouse, embeddings)
    indexing = threading.Thread(
        target=index_periodically,
        args=(indexer, settings.rag.index_interval_seconds, stopped, ready),
        name="knowledge-index",
        daemon=True,
    )
    indexing.start()
    app = create_app(retriever, clickhouse, ready)
    config = Config(app, host="0.0.0.0", port=SEARCH_PORT)
    server = Server(config)
    try:
        await server.serve()
    finally:
        stopped.set()
        indexing.join(timeout=10)
        clickhouse.close()


def main() -> None:
    service = serve_knowledge()
    asyncio.run(service)


if __name__ == "__main__":
    main()
