from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sentinel.agents.sre.commands import CommandRunner
from sentinel.agents.sre.prometheus import query_prometheus as fetch_prometheus
from sentinel.agents.sre.settings import Settings
from sentinel.core.agents.langchain import search_knowledge_tool
from sentinel.core.domain import AgentDomain
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.audit import AuditLog


@dataclass(frozen=True)
class ToolContext:
    settings: Settings
    commands: CommandRunner
    audit: AuditLog
    knowledge: KnowledgeClient
    repository: str
    workspace: Path
    deadline: datetime


class ShellArguments(BaseModel):
    command: str = Field(description="One bounded read-only Linux diagnostic command or pipeline.")
    timeout_seconds: int = Field(default=20, ge=1, le=30, description="Command timeout in seconds.")


@tool(args_schema=ShellArguments)
def run_shell(command: str, timeout_seconds: int, runtime: ToolRuntime[ToolContext]) -> str:
    """Run a bounded read-only diagnostic command in the repository and cluster environment."""
    context = runtime.context
    return context.commands.run(command, timeout_seconds, context.workspace)


class PrometheusArguments(BaseModel):
    query: str = Field(description="PromQL query.")
    start: str | None = Field(default=None, description="Optional RFC3339 or Unix start time.")
    end: str | None = Field(default=None, description="Optional RFC3339 or Unix end time.")
    step: str = Field(default="60s", description="Range query step.")


@tool(args_schema=PrometheusArguments)
def query_prometheus(
    query: str,
    start: str | None,
    end: str | None,
    step: str,
    runtime: ToolRuntime[ToolContext],
) -> dict:
    """Query the configured Prometheus server for alert, metric, or recovery evidence."""
    settings = runtime.context.settings
    secrets = settings.known_secrets()
    return fetch_prometheus(
        settings.prometheus.url,
        query,
        start,
        end,
        step,
        max_bytes=settings.limits.max_tool_output_bytes,
        known_secrets=secrets,
    )


search_knowledge = search_knowledge_tool(
    AgentDomain.SRE,
    "Search historical Sentinel knowledge for a focused investigation question; verify findings against live state.",
)

TOOLS: dict[str, BaseTool] = {
    "query_prometheus": query_prometheus,
    "run_shell": run_shell,
    "search_knowledge": search_knowledge,
}
