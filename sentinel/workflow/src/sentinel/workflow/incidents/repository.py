from typing import Any

from sentinel.core.contracts.incidents import Alert, IncidentResult, ManualActionRequest
from sentinel.core.domain import IncidentStatus
from sentinel.core.persistence.queries import IncidentReader
from sentinel.core.state import incident_rules as rules
from sentinel.core.state.outcomes import Accepted, require_allowed, require_existing, require_transition, succeeded
from sentinel.workflow.incidents.events import (
    AgentResultSaved,
    AlertFired,
    AlertResolved,
    Deleted,
    Ignored,
    ManualActionClaimed,
    ManualActionExpired,
    ManualActionRecorded,
    ReplayRequested,
    RunSkipped,
    RunStarted,
    WorkflowFailed,
)
from sentinel.workflow.incidents.machine import transition
from sentinel.workflow.incidents.snapshot import Incident
from sentinel.workflow.repository import TransitionRepository


class IncidentRepository(TransitionRepository, IncidentReader):
    state_type = Incident
    decide = staticmethod(transition)
    terminal = rules.NOTIFIED

    def new_values(self, repository: str) -> dict[str, Any]:
        return {
            "workflow_id": None,
            "status": IncidentStatus.ACKNOWLEDGED.value,
            "source": "",
            "repository": repository,
            "alert": {},
            "diagnosis": {},
            "pull_request_url": None,
            "replayed_at": None,
            "manual_actions": [],
            "timeline": [],
            "attempts": [],
            "tool_budget": {},
        }

    def queue_alert(self, incident_id: str, alert: Alert, workflow_id: str, repository: str) -> str | None:
        alert_json = alert.model_dump(mode="json")
        event = AlertFired(alert_json, workflow_id, repository)
        outcome = self.apply_transition(incident_id, event, repository)
        return outcome.value if succeeded(outcome) else None

    def resolve_alert(self, incident_id: str, alert: Alert, repository: str) -> None:
        alert_json = alert.model_dump(mode="json")
        event = AlertResolved(alert_json, repository)
        self.apply_transition(incident_id, event, repository)

    def request_replay(self, incident_id: str, workflow_id: str) -> bool:
        event = ReplayRequested(workflow_id)
        outcome = self.apply_transition(incident_id, event)
        require_existing(outcome, f"incident not found: {incident_id}")
        return succeeded(outcome)

    def start_run(self, incident_id: str, workflow_id: str, trigger: str, prompt: str = "") -> bool:
        event = RunStarted(workflow_id, trigger, prompt)
        outcome = self.apply_transition(incident_id, event)
        require_existing(outcome, f"incident not found: {incident_id}")
        return succeeded(outcome)

    def skip_run(self, incident_id: str, workflow_id: str) -> None:
        event = RunSkipped(workflow_id)
        self.apply_transition(incident_id, event)

    def fail_workflow(self, incident_id: str, workflow_id: str, error: str) -> None:
        event = WorkflowFailed(workflow_id, error)
        self.apply_transition(incident_id, event)

    def save_result(self, incident_id: str, result: IncidentResult, workflow_id: str) -> bool:
        result_json = result.model_dump(mode="json")
        event = AgentResultSaved(workflow_id, result_json)
        outcome = self.apply_transition(incident_id, event)
        return isinstance(outcome, Accepted)

    def claim_manual_action(self, request: ManualActionRequest, workflow_id: str, timeout_seconds: int) -> str:
        request_json = request.model_dump(mode="json")
        claim = {**request_json, "workflow_id": workflow_id}
        event = ManualActionClaimed(claim, timeout_seconds)
        outcome = self.apply_transition(request.incident_id, event)
        require_transition(outcome, "incident is no longer actionable")
        return outcome.value

    def record_manual_action(self, incident_id: str, result: dict[str, Any]) -> None:
        event = ManualActionRecorded(result)
        outcome = self.apply_transition(incident_id, event)
        require_transition(outcome, f"incident not found: {incident_id}")

    def expire_manual_action(self, incident_id: str, workflow_id: str, claim_at: str) -> None:
        event = ManualActionExpired(workflow_id, claim_at)
        self.apply_transition(incident_id, event)

    def ignore_incident(self, incident_id: str) -> None:
        event = Ignored()
        outcome = self.apply_transition(incident_id, event)
        require_allowed(outcome)

    def delete_incident(self, incident_id: str) -> None:
        event = Deleted()
        outcome = self.apply_transition(incident_id, event)
        require_allowed(outcome)
