from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sentinel.agents.pr_review.workspace import read_checkout_file
from sentinel.core.agents.langchain import search_knowledge_tool
from sentinel.core.domain import AgentDomain
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.audit import AuditLog


@dataclass(frozen=True)
class ToolContext:
    audit: AuditLog
    knowledge: KnowledgeClient
    repository: str
    deadline: datetime
    checkout: Path | None = None
    max_file_bytes: int = 0


search_knowledge = search_knowledge_tool(
    AgentDomain.PULL_REQUEST_REVIEW,
    "Search historical Sentinel knowledge about this repository; verify findings against the current PR and repository.",
)


class ReadFileArguments(BaseModel):
    file_path: str = Field(description="Repository-relative path of a file at the pull request's head revision.")


@tool(args_schema=ReadFileArguments)
def read_file(file_path: str, runtime: ToolRuntime[ToolContext]) -> str:
    """Read one file of the pull request's head revision, to return its complete fixed content."""
    context = runtime.context
    return read_checkout_file(context.checkout, file_path, context.max_file_bytes)


REVIEW_TOOLS: dict[str, BaseTool] = {"search_knowledge": search_knowledge}
FIX_TOOLS: dict[str, BaseTool] = {**REVIEW_TOOLS, "read_file": read_file}
