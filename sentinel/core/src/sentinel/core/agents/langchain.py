from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ToolCallLimitMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import ToolRuntime
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr
from sentinel.core.agents.audit_middleware import LangChainAuditMiddleware
from sentinel.core.config.settings import LLMConfig
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.core.deadline import remaining_seconds
from sentinel.core.domain import AgentDomain
from sentinel.core.observability.audit import ToolBudget

LIMIT_REFUSAL = "Tool call limit exceeded"


def chat_model(llm: LLMConfig, api_key: SecretStr) -> ChatOpenAI:
    return ChatOpenAI(
        model=llm.model,
        api_key=api_key,
        base_url=llm.base_url,
        max_retries=llm.max_retries,
        timeout=llm.request_timeout_seconds,
        use_responses_api=True,
        output_version="responses/v1",
    )


class RunDeadlineMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        remaining_seconds(request.runtime.context.deadline)
        return handler(request)

    def wrap_tool_call(self, request, handler):
        remaining_seconds(request.runtime.context.deadline)
        return handler(request)


def structured_agent(
    model: ChatOpenAI,
    *,
    cache_key: str,
    tools: Sequence[BaseTool],
    context_schema: type,
    system_prompt: str,
    response_format: type[BaseModel],
    max_tool_calls: int,
) -> Any:
    """An agent that must answer with ``response_format``, audited and bounded to ``max_tool_calls`` per tool and run.

    Its run context carries a ``deadline``: once it passes, the next model or tool call raises ``RunTimedOut``.

    Each tool has its own limit so the structured answer, itself a tool call, is never refused: a call past
    the limit returns to the model as an error and the model answers with the evidence it has. A
    ``ToolException`` (a refused or failed command) also returns to the model as the tool's error result;
    any other exception still fails the run.
    """
    cached = model.bind(prompt_cache_key=cache_key)
    strategy = ToolStrategy(response_format)
    tool_limits = [
        ToolCallLimitMiddleware(tool_name=item.name, run_limit=max_tool_calls, exit_behavior="continue")
        for item in tools
    ]
    audit = LangChainAuditMiddleware()
    deadline = RunDeadlineMiddleware()
    recoverable_tools = [item.model_copy(update={"handle_tool_error": True}) for item in tools]
    return create_agent(
        model=cached,
        tools=recoverable_tools,
        context_schema=context_schema,
        system_prompt=system_prompt,
        response_format=strategy,
        middleware=[*tool_limits, audit, deadline],
    )


def tool_budget(messages: Sequence[BaseMessage], tool_names: Sequence[str], max_tool_calls: int) -> ToolBudget:
    calls = dict.fromkeys(tool_names, 0)
    exhausted: list[str] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name not in calls:
            continue
        content = str(message.content)
        refused = message.status == "error" and content.startswith(LIMIT_REFUSAL)
        if not refused:
            calls[message.name] += 1
        elif message.name not in exhausted:
            exhausted.append(message.name)
    return ToolBudget(limit=max_tool_calls, calls=calls, exhausted_tools=exhausted)


def reference_material(rag_context: Sequence[RetrievedContext]) -> str:
    if not rag_context:
        return ""
    excerpts = "\n\n".join(f"Source: {item.source}\n{item.content}" for item in rag_context)
    return f"\n\nRetrieved reference material (verify against the current repository and live state):\n{excerpts}"


def search_knowledge_tool(domain: AgentDomain, description: str) -> BaseTool:
    @tool("search_knowledge", description=description)
    def search_knowledge(query: str, runtime: ToolRuntime) -> str:
        context = runtime.context
        search = KnowledgeSearchRequest(query=query, domain=domain, repository=context.repository)
        return context.knowledge.search_text(search, context.audit)

    return search_knowledge
