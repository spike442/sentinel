import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sentinel.agents.sre.commands import CommandRunner
from sentinel.agents.sre.settings import Settings
from sentinel.agents.sre.tools import TOOLS, ToolContext
from sentinel.core.agents.langchain import chat_model, reference_material, structured_agent, tool_budget
from sentinel.core.agents.prompts import PromptStore
from sentinel.core.contracts.history import PriorAttempt
from sentinel.core.contracts.incidents import Diagnosis, PreparedIncident
from sentinel.core.deadline import remaining_seconds
from sentinel.core.digest import text_digest
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.audit import AuditLog


def replay_history(history: list[PriorAttempt]) -> str:
    lines = ["Previous attempts for this incident:"]
    for attempt in history:
        lines.append(f"- Attempt {attempt.number} ({attempt.trigger}) at {attempt.started_at}: {attempt.status}")
        if attempt.prompt:
            lines.append(f"  operator instruction: {attempt.prompt}")
        diagnosis = attempt.result.get("diagnosis", {})
        if diagnosis.get("hypothesis"):
            lines.append(f"  hypothesis: {diagnosis['hypothesis']}")
        if diagnosis.get("proposed_files"):
            lines.append(f"  proposed files: {', '.join(diagnosis['proposed_files'])}")
        if diagnosis.get("manual_actions"):
            lines.append("  manual actions were proposed")
        if attempt.result.get("error"):
            lines.append(f"  error: {attempt.result['error']}")
    return "\n".join(lines)


def operator_prompt(prompt: str, history: list[PriorAttempt]) -> str | None:
    if not history:
        return prompt or None
    previous = replay_history(history)
    return f"{previous}\n\n{prompt}" if prompt else previous


class DiagnosisAgent:
    def __init__(self, settings: Settings, prompts: PromptStore, commands: CommandRunner, knowledge: KnowledgeClient):
        self.settings = settings
        self.prompts = prompts
        self.commands = commands
        self.knowledge = knowledge
        self.model = chat_model(settings.llm, settings.openai_api_key)
        self._agents: dict[str, Any] = {}

    def diagnose(self, request: PreparedIncident, workspace: Path, audit: AuditLog, deadline: datetime) -> Diagnosis:
        repository = request.repository.name
        agent = self._agent_for(repository)
        replay_prompt = operator_prompt(request.prompt, request.history)
        prompt = self._request(request, replay_prompt)
        context = ToolContext(
            settings=self.settings,
            commands=self.commands,
            audit=audit,
            knowledge=self.knowledge,
            repository=repository,
            workspace=workspace,
            deadline=deadline,
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={
                "run_name": f"sre-investigation-{request.incident_id}",
                "tags": ["sre", request.alert.source or "unknown"],
                "metadata": {"incident_id": request.incident_id, "repository": repository},
            },
            context=context,
        )
        remaining_seconds(deadline)
        tool_names = list(TOOLS)
        budget = tool_budget(result["messages"], tool_names, self.settings.limits.max_tool_calls)
        audit.record_tool_budget(budget)
        diagnosis = result.get("structured_response")
        if not isinstance(diagnosis, Diagnosis):
            raise ValueError("LangChain did not return a structured diagnosis")
        completed = diagnosis.model_dump(mode="json")
        audit.record("diagnosis_completed", completed)
        return diagnosis

    def _agent_for(self, repository: str) -> Any:
        agent = self._agents.get(repository)
        if agent is None:
            agent = self._build_agent(repository)
            self._agents[repository] = agent
        return agent

    def _build_agent(self, repository: str) -> Any:
        system_prompt = self.prompts.load_text(repository, "sre", "system.md")
        investigation_prompt = self.prompts.load_text(repository, "sre", "actions/investigate.md")
        tool_instructions = []
        for tool_name in TOOLS:
            instructions = self.prompts.load_text(repository, "sre", f"actions/{tool_name}.md")
            tool_instructions.append(f"{tool_name} instructions:\n{instructions}")
        tool_prompts = "\n\n".join(tool_instructions)
        instructions = f"{system_prompt}\n\nInvestigation instructions:\n{investigation_prompt}\n\n{tool_prompts}"
        prompt_version = text_digest(instructions)
        return structured_agent(
            self.model,
            cache_key=f"sre:{repository}:{prompt_version[:16]}",
            tools=TOOLS.values(),
            context_schema=ToolContext,
            system_prompt=instructions,
            response_format=Diagnosis,
            max_tool_calls=self.settings.limits.max_tool_calls,
        )

    def _request(self, request: PreparedIncident, replay_prompt: str | None) -> str:
        alert_fields = request.alert.model_dump(mode="json")
        alert_json = json.dumps(alert_fields, indent=2, sort_keys=True)
        references = reference_material(request.rag_context)
        message = f"Investigate this alert and follow the diagnosis workflow.\n\nAlert:\n{alert_json}{references}"
        if replay_prompt:
            template = self.prompts.load_text(request.repository.name, "sre", "actions/replay.md")
            message += "\n\n" + template.replace("{{operator_prompt}}", replay_prompt)
        return message

    def close(self) -> None:
        self.model.root_client.close()
