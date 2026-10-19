from sentinel.core.contracts.knowledge import RetrievedContext
from sentinel.knowledge.clickhouse import ClickHouse
from sentinel.knowledge.config import KnowledgeSettings
from sentinel.knowledge.rag.clickhouse_index import KnowledgeIndexStore
from sentinel.knowledge.rag.embeddings import Embeddings


class RagRetriever:
    def __init__(self, settings: KnowledgeSettings, database: ClickHouse, embeddings: Embeddings):
        self.config = settings.rag
        self.store = KnowledgeIndexStore(database)
        self.embeddings = embeddings

    def retrieve_context(self, domain: str, repository: str, query: str) -> list[RetrievedContext]:
        embedding = self.embeddings.embed_query(query)
        rows = self.store.search_chunks(domain, repository, embedding, self.config.candidate_results)
        contexts = []
        seen_content = set()
        budget = self.config.max_context_tokens
        for row in rows:
            content = row["content"]
            if content in seen_content:
                continue
            length = self.embeddings.count_tokens(content)
            if length > budget:
                continue
            seen_content.add(content)
            context = RetrievedContext(content=content, source=row["source"], score=row["score"])
            contexts.append(context)
            budget -= length
            if len(contexts) == self.config.max_results:
                break
        return contexts
