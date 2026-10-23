from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, SecretStr
from sentinel.agents.framework.langchain import chat_model, structured_agent, tool_budget
from sentinel.agents.framework.prompts import PromptStore
from sentinel.core.config.settings import LLMConfig
from sentinel.core.deadline import remaining_seconds
from sentinel.core.digest import text_digest
from sentinel.core.observability.audit import AuditLog


class AgentConfig(BaseModel):
    llm: LLMConfig
    max_tool_calls: int = Field(gt=0)


@dataclass(frozen=True)
class RunContext:
    audit: AuditLog
    deadline: datetime


@dataclass(frozen=True)
class AgentTask[Answer: BaseModel]:
    """One job an agent does: its prompts under ``context/<scope>/prompts/<agent>/``, tools, and structured answer.

    The system prompt is ``system.md``, then ``actions/<action>.md``, then ``actions/<tool>.md`` for every tool.
    """

    agent: str
    action: str
    tools: Mapping[str, BaseTool]
    context_schema: type[RunContext]
    answer: type[Answer]


@dataclass(frozen=True)
class AgentRun:
    scope: str
    message: str
    context: RunContext
    name: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunner:
    def __init__(self, config: AgentConfig, api_key: SecretStr, prompts: PromptStore):
        self.config = config
        self.prompts = prompts
        self.model = chat_model(config.llm, api_key)
        self._agents: dict[tuple[str, str, str], Any] = {}

    def run[Answer: BaseModel](self, task: AgentTask[Answer], run: AgentRun) -> Answer:
        agent = self._agent_for(task, run.scope)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": run.message}]},
            config={"run_name": run.name, "tags": run.tags, "metadata": run.metadata},
            context=run.context,
        )
        remaining_seconds(run.context.deadline)
        tool_names = list(task.tools)
        budget = tool_budget(result["messages"], tool_names, self.config.max_tool_calls)
        run.context.audit.record_tool_budget(budget)
        answer = result.get("structured_response")
        if not isinstance(answer, task.answer):
            raise ValueError(f"LangChain did not return a structured {task.agent} {task.action} answer")
        return answer

    def load_prompt(self, task: AgentTask, scope: str, name: str) -> str:
        return self.prompts.load_text(scope, task.agent, name)

    def _agent_for(self, task: AgentTask, scope: str) -> Any:
        key = (task.agent, task.action, scope)
        agent = self._agents.get(key)
        if agent is None:
            agent = self._build_agent(task, scope)
            self._agents[key] = agent
        return agent

    def _build_agent(self, task: AgentTask, scope: str) -> Any:
        system_prompt = self.load_prompt(task, scope, "system.md")
        action_prompt = self.load_prompt(task, scope, f"actions/{task.action}.md")
        tool_instructions = []
        for tool_name in task.tools:
            instructions = self.load_prompt(task, scope, f"actions/{tool_name}.md")
            tool_instructions.append(f"{tool_name} instructions:\n{instructions}")
        tool_prompts = "\n\n".join(tool_instructions)
        heading = task.action.capitalize()
        instructions = f"{system_prompt}\n\n{heading} instructions:\n{action_prompt}\n\n{tool_prompts}"
        prompt_version = text_digest(instructions)
        return structured_agent(
            self.model,
            cache_key=f"{task.agent}:{task.action}:{scope}:{prompt_version[:16]}",
            tools=list(task.tools.values()),
            context_schema=task.context_schema,
            system_prompt=instructions,
            response_format=task.answer,
            max_tool_calls=self.config.max_tool_calls,
        )

    def close(self) -> None:
        self.model.root_client.close()
