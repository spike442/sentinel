from sentinel.core.config.workflow import IncidentSettings
from sentinel.core.contracts.executor import PullRequestCreated
from sentinel.core.contracts.incidents import IncidentResult
from sentinel.core.domain import IncidentStatus
from sentinel.core.kafka.contracts import ExecutorAction, ExecutorReturn
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.sre.incidents import fix_policy
from sentinel.workflow.sre.incidents.repository import IncidentRepository


class FixSubmission:
    def __init__(self, settings: IncidentSettings, incidents: IncidentRepository, messages: DomainMessages):
        self.policy = settings.incident
        self.repository = settings.incident_repository
        self.incidents = incidents
        self.messages = messages

    def submit_fix(self, incident_id: str, result: IncidentResult, workflow_id: str) -> None:
        decided = fix_policy.decide(result)
        publishing = result.model_copy(update={"status": IncidentStatus.RUNNING})
        saved = self.incidents.save_result(incident_id, decided or publishing, workflow_id)
        if saved and decided is None:
            self._send_request(incident_id, result, workflow_id)

    def on_executor_return(self, executor_return: ExecutorReturn) -> None:
        incident_id = executor_return.record_id
        incident = self.incidents.get(incident_id)
        if incident is None:
            return
        result = IncidentResult(
            status=incident["status"], diagnosis=incident["diagnosis"], tool_budget=incident["tool_budget"]
        )
        if executor_return.result is None:
            reason = executor_return.error or "ExecutorFailed"
            submitted = fix_policy.failed(result, reason)
        else:
            created = PullRequestCreated.model_validate(executor_return.result)
            submitted = fix_policy.submitted(result, created)
        self.incidents.save_result(incident_id, submitted, executor_return.workflow_id)

    def _send_request(self, incident_id: str, result: IncidentResult, workflow_id: str) -> None:
        request = fix_policy.pull_request_request(
            result, self.repository, self.repository.branch, self.policy.branch_prefix
        )
        self.messages.command_executor(ExecutorAction.CREATE_PULL_REQUEST, incident_id, workflow_id, request)
