from datetime import UTC, datetime
from time import time_ns
from uuid import uuid4

from sentinel.core.digest import text_digest
from sentinel.knowledge.clickhouse import ClickHouse
from sentinel.knowledge.rag.documents import KnowledgeDocument

LIVE_DOCUMENTS = "knowledge_documents FINAL WHERE NOT is_deleted"
SCORED_CHUNKS = (
    "SELECT source_id, toString(generation) AS generation, chunk_number, object_key, content, "
    "1 - cosineDistance(embedding, {embedding:Array(Float32)}) AS score FROM knowledge_chunks"
)


def is_unchanged(indexed: dict | None, document: KnowledgeDocument, checksum: str, signature: str) -> bool:
    return indexed == {
        "source_revision": document.revision,
        "content_hash": checksum,
        "index_signature": signature,
        "domains": document.domains,
        "repository": document.repository,
    }


class KnowledgeIndexStore:
    def __init__(self, database: ClickHouse):
        self.database = database

    def indexed_documents(self) -> dict[str, dict]:
        rows = self.database.query(
            "SELECT source_id, source_revision, content_hash, index_signature, domains, repository "
            f"FROM {LIVE_DOCUMENTS}"
        )
        return {row.pop("source_id"): row for row in rows}

    def replace_document(
        self,
        document: KnowledgeDocument,
        checksum: str,
        signature: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        source_id = text_digest(document.key)
        generation = uuid4()
        pairs = zip(chunks, embeddings, strict=True)
        chunk_rows = [
            [source_id, generation, number, document.key, content, vector]
            for number, (content, vector) in enumerate(pairs)
        ]
        chunk_columns = ["source_id", "generation", "chunk_number", "object_key", "content", "embedding"]
        self.database.insert("knowledge_chunks", chunk_rows, chunk_columns)
        self.database.insert(
            "knowledge_documents",
            [
                [
                    source_id,
                    generation,
                    document.key,
                    document.domains,
                    document.repository,
                    document.revision,
                    checksum,
                    signature,
                    document.content,
                    time_ns(),
                    0,
                    datetime.now(UTC),
                ]
            ],
            [
                "source_id",
                "generation",
                "object_key",
                "domains",
                "repository",
                "source_revision",
                "content_hash",
                "index_signature",
                "content",
                "version",
                "is_deleted",
                "indexed_at",
            ],
        )

    def retire_missing(self, keys: set[str]) -> int:
        active_ids = {text_digest(key) for key in keys}
        rows = self.database.query(f"SELECT * FROM {LIVE_DOCUMENTS}")
        retired = 0
        for row in rows:
            if row["source_id"] in active_ids:
                continue
            version = time_ns()
            indexed_at = datetime.now(UTC)
            row.update(version=version, is_deleted=1, indexed_at=indexed_at)
            columns = list(row)
            values = [row[column] for column in columns]
            self.database.insert("knowledge_documents", [values], columns)
            retired += 1
        return retired

    def prune_chunks(self) -> None:
        self.database.command(
            "ALTER TABLE knowledge_chunks DELETE WHERE (source_id, generation) NOT IN "
            f"(SELECT source_id, generation FROM {LIVE_DOCUMENTS})"
        )

    def search_chunks(self, domain: str, repository: str, embedding: list[float], candidates: int) -> list[dict]:
        rows = self.database.query(
            f"{SCORED_CHUNKS} WHERE (source_id, generation) IN (SELECT source_id, generation FROM {LIVE_DOCUMENTS} "
            "AND has(domains, {domain:String}) AND repository = {repository:String}) "
            "ORDER BY cosineDistance(embedding, {embedding:Array(Float32)}) ASC, source_id, chunk_number "
            "LIMIT {limit:UInt32}",
            {"domain": domain, "repository": repository, "embedding": embedding, "limit": candidates},
        )
        return [{**row, "source": f"{row['object_key']}#chunk-{row['chunk_number']}"} for row in rows]
