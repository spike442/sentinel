from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class KnowledgeDocument:
    key: str
    domains: list[str]
    repository: str
    revision: str
    content: str
