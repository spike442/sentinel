from pydantic import BaseModel, Field
from sentinel.core.domain import AgentDomain


class RetrievedContext(BaseModel):
    content: str
    source: str
    score: float


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    domain: AgentDomain
    repository: str = Field(min_length=1)
