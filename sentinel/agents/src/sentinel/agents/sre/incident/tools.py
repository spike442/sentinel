from dataclasses import dataclass
from pathlib import Path

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sentinel.agents.framework.knowledge import KnowledgeContext, search_knowledge_tool
from sentinel.agents.sre.incident.commands import CommandRunner
from sentinel.agents.sre.incident.prometheus import Prometheus
from sentinel.core.domain import AgentDomain


@dataclass(frozen=True)
class ToolContext(KnowledgeContext):
    commands: CommandRunner
    prometheus: Prometheus
    workspace: Path


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
    return runtime.context.prometheus.query(query, start, end, step)


search_knowledge = search_knowledge_tool(
    AgentDomain.SRE,
    "Search historical Sentinel knowledge for a focused investigation question; verify findings against live state.",
)

TOOLS: dict[str, BaseTool] = {
    "query_prometheus": query_prometheus,
    "run_shell": run_shell,
    "search_knowledge": search_knowledge,
}
