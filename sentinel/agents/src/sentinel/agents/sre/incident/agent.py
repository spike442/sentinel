import json
from datetime import datetime
from pathlib import Path

from sentinel.agents.framework.knowledge import reference_material
from sentinel.agents.framework.runner import AgentRun, AgentRunner, AgentTask
from sentinel.agents.sre.incident.commands import CommandRunner
from sentinel.agents.sre.incident.prometheus import Prometheus
from sentinel.agents.sre.incident.tools import TOOLS, ToolContext
from sentinel.core.contracts.history import PriorAttempt
from sentinel.core.contracts.incidents import Diagnosis, PreparedIncident
from sentinel.core.domain import AgentDomain
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.audit import AuditLog

INVESTIGATE = AgentTask(
    agent=AgentDomain.SRE.value,
    action="investigate",
    tools=TOOLS,
    context_schema=ToolContext,
    answer=Diagnosis,
)


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
    def __init__(
        self, runner: AgentRunner, commands: CommandRunner, prometheus: Prometheus, knowledge: KnowledgeClient
    ):
        self.runner = runner
        self.commands = commands
        self.prometheus = prometheus
        self.knowledge = knowledge

    def diagnose(self, request: PreparedIncident, workspace: Path, audit: AuditLog, deadline: datetime) -> Diagnosis:
        repository = request.repository.name
        replay_prompt = operator_prompt(request.prompt, request.history)
        message = self._request(request, replay_prompt)
        context = ToolContext(
            audit=audit,
            deadline=deadline,
            knowledge=self.knowledge,
            repository=repository,
            commands=self.commands,
            prometheus=self.prometheus,
            workspace=workspace,
        )
        run = AgentRun(
            scope=repository,
            message=message,
            context=context,
            name=f"sre-investigation-{request.incident_id}",
            tags=["sre", request.alert.source or "unknown"],
            metadata={"incident_id": request.incident_id, "repository": repository},
        )
        diagnosis = self.runner.run(INVESTIGATE, run)
        completed = diagnosis.model_dump(mode="json")
        audit.record("diagnosis_completed", completed)
        return diagnosis

    def _request(self, request: PreparedIncident, replay_prompt: str | None) -> str:
        alert_fields = request.alert.model_dump(mode="json")
        alert_json = json.dumps(alert_fields, indent=2, sort_keys=True)
        references = reference_material(request.rag_context)
        message = f"Investigate this alert and follow the diagnosis workflow.\n\nAlert:\n{alert_json}{references}"
        if replay_prompt:
            template = self.runner.load_prompt(INVESTIGATE, request.repository.name, "actions/replay.md")
            message += "\n\n" + template.replace("{{operator_prompt}}", replay_prompt)
        return message
