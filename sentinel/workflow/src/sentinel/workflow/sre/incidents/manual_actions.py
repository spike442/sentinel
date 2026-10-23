import logging
from datetime import datetime

from sentinel.core.config.workflow import IncidentSettings
from sentinel.core.contracts.executor import RunCommand
from sentinel.core.contracts.incidents import ActionOutput, ClaimedAction, ManualActionRequest
from sentinel.core.domain import ActionStatus
from sentinel.core.kafka.contracts import ExecutorAction, ExecutorReturn, WorkflowRequest
from sentinel.core.state import incident_rules as rules
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.sre.incidents.repository import IncidentRepository

logger = logging.getLogger(__name__)


def _prior_claim(incident: dict, workflow_id: str) -> dict | None:
    for action in incident["manual_actions"]:
        if action["workflow_id"] == workflow_id:
            return action
    return None


class ManualActions:
    def __init__(self, settings: IncidentSettings, incidents: IncidentRepository, messages: DomainMessages):
        self.timeout_seconds = settings.incident.manual_action_timeout_seconds
        self.incidents = incidents
        self.messages = messages

    def on_request(self, workflow_request: WorkflowRequest) -> None:
        request = ManualActionRequest.model_validate(workflow_request.payload)
        workflow_id = workflow_request.workflow_id
        claimed = self.claim_action(request, workflow_id)
        if claimed is None:
            return
        command = RunCommand(command=claimed.action.command, timeout_seconds=self.timeout_seconds)
        self.messages.command_executor(
            ExecutorAction.RUN_COMMAND, request.incident_id, workflow_id, command, context=claimed
        )

    def claim_action(self, request: ManualActionRequest, workflow_id: str) -> ClaimedAction | None:
        current = self.incidents.get(request.incident_id)
        if current is None:
            logger.warning("Manual action for a deleted incident incident_id=%s", request.incident_id)
            return None
        prior = _prior_claim(current, workflow_id)
        if prior and prior["status"] != ActionStatus.RUNNING.value:
            return None
        if prior:
            claim_at = prior["claim_at"]
        else:
            claim_at = self.incidents.claim_manual_action(request, workflow_id, self.timeout_seconds)
        request_fields = request.model_dump()
        return ClaimedAction(**request_fields, claim_at=claim_at)

    def on_executor_return(self, executor_return: ExecutorReturn) -> None:
        claimed = ClaimedAction.model_validate(executor_return.context)
        workflow_id = executor_return.workflow_id
        if executor_return.result is None:
            output = ActionOutput(status=ActionStatus.FAILED, error="ExecutorFailed")
        else:
            output = ActionOutput.model_validate(executor_return.result)
        action_fields = claimed.action.model_dump(mode="json")
        output_fields = output.model_dump(mode="json", exclude_none=True)
        entry = {
            **action_fields,
            **output_fields,
            "action_index": claimed.action_index,
            "approval_id": claimed.approval_id,
            "workflow_id": workflow_id,
            "claim_at": claimed.claim_at,
        }
        self.incidents.record_manual_action(claimed.incident_id, entry)

    def expire_actions(self, now: datetime) -> None:
        incidents = self.incidents.running_manual_actions()
        for incident in incidents:
            for action in incident["manual_actions"]:
                timed_out = rules.action_timed_out(action, now, self.timeout_seconds)
                if not timed_out:
                    continue
                self.incidents.expire_manual_action(incident["id"], action["workflow_id"], action["claim_at"])
