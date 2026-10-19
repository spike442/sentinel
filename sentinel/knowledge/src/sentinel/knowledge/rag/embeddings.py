from collections.abc import Sequence

from fastembed import TextEmbedding
from sentinel.knowledge.config import RagConfig
from tokenizers import Tokenizer


class Embeddings:
    def __init__(self, config: RagConfig):
        self.config = config
        tokenizer_path = config.embedding_model_path / "tokenizer.json"
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.model = TextEmbedding(
            model_name=config.embedding_model,
            specific_model_path=str(config.embedding_model_path),
            threads=2,
        )

    def count_tokens(self, content: str) -> int:
        return len(self.tokenizer.encode(content, add_special_tokens=False).ids)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embed_texts([f"{self.config.document_prefix}{text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        encoded = self.tokenizer.encode(text, add_special_tokens=False)
        if len(encoded.ids) > self.config.chunk_tokens:
            encoded.truncate(self.config.chunk_tokens)
            text = self.tokenizer.decode(encoded.ids)
        return self.embed_texts([f"{self.config.query_prefix}{text}"])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embedded = self.model.embed(texts, batch_size=self.config.batch_size)
        return [vector.tolist() for vector in embedded]
