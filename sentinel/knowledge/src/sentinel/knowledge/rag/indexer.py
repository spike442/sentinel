from importlib.metadata import version

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentinel.core.digest import json_digest, text_digest
from sentinel.knowledge.clickhouse import ClickHouse
from sentinel.knowledge.config import KnowledgeSettings
from sentinel.knowledge.rag.clickhouse_index import KnowledgeIndexStore, is_unchanged
from sentinel.knowledge.rag.documents import KnowledgeDocument
from sentinel.knowledge.rag.embeddings import Embeddings
from sentinel.knowledge.rag.s3_source import S3KnowledgeSource


class RagIndexer:
    def __init__(self, settings: KnowledgeSettings, clickhouse: ClickHouse, embeddings: Embeddings):
        self.settings = settings
        self.store = KnowledgeIndexStore(clickhouse)
        self.embeddings = embeddings
        rag = settings.rag
        self.signature = json_digest(
            {
                "backend": version("fastembed"),
                "model": rag.embedding_model,
                "revision": rag.embedding_revision,
                "chunk_tokens": rag.chunk_tokens,
                "overlap_tokens": rag.overlap_tokens,
                "document_prefix": rag.document_prefix,
                "query_prefix": rag.query_prefix,
            }
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_tokens,
            chunk_overlap=settings.rag.overlap_tokens,
            length_function=self.embeddings.count_tokens,
            separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
        )

    def source_documents(self):
        secret_access_key = self.settings.s3_secret_access_key.get_secret_value()
        for config in self.settings.rag.sources:
            source = S3KnowledgeSource(self.settings.s3, config, self.settings.s3_access_key_id, secret_access_key)
            domains = [domain.value for domain in config.domains]
            try:
                objects = source.list_objects()
                for key, revision in objects:
                    content = source.read_object(key)
                    yield KnowledgeDocument(
                        key=key,
                        domains=domains,
                        repository=config.repository,
                        revision=revision,
                        content=content,
                    )
            finally:
                source.close()

    def index_documents(self) -> int:
        indexed = 0
        keys = set()
        current = self.store.indexed_documents()
        documents = self.source_documents()
        for document in documents:
            keys.add(document.key)
            checksum = text_digest(document.content)
            source_id = text_digest(document.key)
            indexed_state = current.get(source_id)
            if is_unchanged(indexed_state, document, checksum, self.signature):
                continue
            chunks = self.splitter.split_text(document.content)
            vectors = self.embeddings.embed_documents(chunks)
            self.store.replace_document(document, checksum, self.signature, chunks, vectors)
            indexed += 1
        retired = self.store.retire_missing(keys)
        if indexed or retired:
            self.store.prune_chunks()
        return indexed
