from typing import Any

from fastapi import Request
from sentinel.api.domains.contract import ActionPrompt, ActionRequest, RecordAction, RecordLink, Tone
from sentinel.api.domains.workflow import RecordWorkflow
from sentinel.api.requests import IncidentWorkflowRequests
from sentinel.core.domain import AgentDomain, IncidentStatus
from sentinel.core.errors import Conflict
from sentinel.core.persistence.queries import IncidentReader
from sentinel.core.state import history
from sentinel.core.state import incident_rules as rules
from sentinel.core.state.workflows import INCIDENT_FLOW

REPLAY_BLOCKED = "Tell the agent what to reconsider before replaying this blocked incident"

TONES = {
    IncidentStatus.ACKNOWLEDGED.value: Tone.ACTIVE,
    IncidentStatus.REOPENED.value: Tone.ACTIVE,
    IncidentStatus.RUNNING.value: Tone.ACTIVE,
    IncidentStatus.AWAITING.value: Tone.WAITING,
    IncidentStatus.BLOCKED.value: Tone.WAITING,
    IncidentStatus.RESOLVED.value: Tone.DONE,
    IncidentStatus.FAILED.value: Tone.FAILED,
    IncidentStatus.IGNORED.value: Tone.CLOSED,
    IncidentStatus.SKIPPED.value: Tone.CLOSED,
    history.SUPERSEDED: Tone.CLOSED,
}


def blocked(record: dict[str, Any]) -> bool:
    return record["status"] == IncidentStatus.BLOCKED.value


class IncidentWorkflow(RecordWorkflow):
    id = "incidents"
    label = "Incidents"
    agent = AgentDomain.SRE
    statuses = IncidentStatus
    flow = INCIDENT_FLOW
    tones = TONES
    reader_type = IncidentReader

    def title(self, record: dict[str, Any]) -> str:
        annotations = record["alert"].get("annotations", {})
        return annotations.get("summary") or record["diagnosis"].get("incident") or record["id"]

    def actions(self, record: dict[str, Any]) -> list[RecordAction]:
        status = record["status"]
        actions = []
        if status in rules.REPLAYABLE:
            prompt = ActionPrompt(message=REPLAY_BLOCKED, required=True) if blocked(record) else None
            actions.append(RecordAction(name="replay", label="Replay", prompt=prompt))
        if status not in rules.CLOSED:
            actions.append(RecordAction(name="ignore", label="Ignore"))
        if blocked(record) and record["diagnosis"].get("manual_actions"):
            actions.append(RecordAction(name="manual-action", label="Approve & run"))
        confirm = "Delete this incident and its history?"
        actions.append(RecordAction(name="delete", label="Delete", tone="danger", confirm=confirm))
        return actions

    def links(self, record: dict[str, Any]) -> list[RecordLink]:
        review_id = record.get("review_id")
        if not review_id:
            return []
        return [RecordLink(domain=AgentDomain.SRE.value, workflow="reviews", record_id=review_id, label="Fix review")]

    async def run_action(self, request: Request, record: dict[str, Any], name: str, body: ActionRequest) -> str:
        incident_id = record["id"]
        requests = IncidentWorkflowRequests(self.reader(request), request.app.state.settings)
        prompt = body.prompt.strip()
        if name == "replay":
            if blocked(record) and not prompt:
                raise Conflict("replaying a blocked incident needs an instruction")
            return await requests.replay_incident(incident_id, prompt)
        if name == "ignore":
            return await requests.ignore_incident(incident_id)
        if name == "manual-action":
            if body.action_index is None:
                raise Conflict("a manual action needs its action_index")
            return await requests.execute_manual_action(incident_id, body.action_index)
        return await requests.delete_incident(incident_id)
