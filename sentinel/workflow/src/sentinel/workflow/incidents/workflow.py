"""Incident components and the messages each owns.

``Investigation`` (cluster alerts, agent runs, timeouts), ``FixSubmission`` (fix pull requests), and
``ManualActions`` (operator-approved commands) apply their changes through the incident state machine
and reach agents, sentinel-executor, and Spark through ``DomainMessages``.
"""

from datetime import UTC, datetime
from typing import Any

from sentinel.core.config.workflow import IncidentSettings
from sentinel.core.contracts.incidents import IncidentRequest
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import (
    AgentReturn,
    ExecutorAction,
    ExecutorReturn,
    KafkaTopic,
    RequestKind,
    WorkflowRequest,
)
from sentinel.core.knowledge import KnowledgeClient
from sentinel.workflow.discord import DiscordWebhook
from sentinel.workflow.incidents.alertmanager import AlertmanagerClient
from sentinel.workflow.incidents.investigation import Investigation
from sentinel.workflow.incidents.manual_actions import ManualActions
from sentinel.workflow.incidents.repository import IncidentRepository
from sentinel.workflow.incidents.submission import FixSubmission
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.routing import DomainWorkflow


def incident_notice(incident: dict[str, Any]) -> str:
    labels = incident["alert"].get("labels", {})
    where = " · ".join(value for value in (labels.get("alertname"), labels.get("namespace")) if value)
    lines = [f"**Incident {incident['status']}** · {where or incident['id']}"]
    hypothesis = incident["diagnosis"].get("hypothesis")
    if hypothesis:
        lines.append(hypothesis)
    if incident["pull_request_url"]:
        lines.append(incident["pull_request_url"])
    return "\n".join(lines)


class IncidentWorkflow(DomainWorkflow):
    def __init__(
        self,
        settings: IncidentSettings,
        incidents: IncidentRepository,
        knowledge: KnowledgeClient,
        alertmanager: AlertmanagerClient,
        discord: DiscordWebhook,
    ):
        messages = DomainMessages(
            settings,
            AgentDomain.SRE,
            KafkaTopic.SRE_COMMANDS,
            RequestKind.INCIDENT,
            records=incidents,
            describe=incident_notice,
            discord=discord,
        )
        incidents.on_terminal = messages.notify
        self.incidents = incidents
        self.messages = messages
        self.submission = FixSubmission(settings, incidents, messages)
        self.manual_actions = ManualActions(settings, incidents, messages)
        self.investigation = Investigation(
            settings, incidents, knowledge, alertmanager=alertmanager, messages=messages, submission=self.submission
        )
        super().__init__(
            AgentDomain.SRE,
            topics={
                KafkaTopic.CLUSTER_ALERTS: self.investigation.on_cluster_alert,
                KafkaTopic.SRE_RETURNS: self.investigation.on_agent_return,
            },
            requests={
                RequestKind.INCIDENT: self.investigation.on_request,
                RequestKind.MANUAL_ACTION: self.manual_actions.on_request,
                RequestKind.IGNORE: self._on_ignore,
                RequestKind.DELETE: self._on_delete,
            },
            executor_returns={
                ExecutorAction.CREATE_PULL_REQUEST: self.submission.on_executor_return,
                ExecutorAction.RUN_COMMAND: self.manual_actions.on_executor_return,
            },
        )

    def fail_record(self, topic: KafkaTopic, payload: dict[str, Any], error: str) -> None:
        if topic is KafkaTopic.SRE_RETURNS:
            agent_return = AgentReturn.model_validate(payload)
            incident_id = IncidentRequest.model_validate(agent_return.request).incident_id
            workflow_id = agent_return.workflow_id
        elif topic is KafkaTopic.WORKFLOW_REQUESTS:
            request = WorkflowRequest.model_validate(payload)
            incident_id = request.payload["incident_id"]
            workflow_id = request.workflow_id
        elif topic is KafkaTopic.EXECUTOR_RETURNS:
            executor_return = ExecutorReturn.model_validate(payload)
            incident_id = executor_return.context["incident_id"]
            workflow_id = executor_return.workflow_id
        else:
            return
        self.incidents.fail_workflow(incident_id, workflow_id, error)
        self.messages.announce_outcome(incident_id, workflow_id)

    def expire_workflows(self) -> None:
        now = datetime.now(UTC)
        self.investigation.expire_investigations(now)
        self.manual_actions.expire_actions(now)

    def _on_ignore(self, request: WorkflowRequest) -> None:
        self.incidents.ignore_incident(request.payload["incident_id"])

    def _on_delete(self, request: WorkflowRequest) -> None:
        self.incidents.delete_incident(request.payload["incident_id"])
