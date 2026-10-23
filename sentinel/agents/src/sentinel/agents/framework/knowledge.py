from collections.abc import Sequence
from dataclasses import dataclass

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from sentinel.agents.framework.runner import RunContext
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.core.domain import AgentDomain
from sentinel.core.knowledge import KnowledgeClient


@dataclass(frozen=True)
class KnowledgeContext(RunContext):
    knowledge: KnowledgeClient
    repository: str


def reference_material(rag_context: Sequence[RetrievedContext]) -> str:
    if not rag_context:
        return ""
    excerpts = "\n\n".join(f"Source: {item.source}\n{item.content}" for item in rag_context)
    return f"\n\nRetrieved reference material (verify against the current repository and live state):\n{excerpts}"


def search_knowledge_tool(domain: AgentDomain, description: str) -> BaseTool:
    @tool("search_knowledge", description=description)
    def search_knowledge(query: str, runtime: ToolRuntime[KnowledgeContext]) -> str:
        context = runtime.context
        search = KnowledgeSearchRequest(query=query, domain=domain, repository=context.repository)
        return context.knowledge.search_text(search, context.audit)

    return search_knowledge
