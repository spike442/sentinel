"""Incident components and the messages each owns.

``Investigation`` (cluster alerts, agent runs, timeouts), ``FixSubmission`` (fix pull requests), and
``ManualActions`` (operator-approved commands) apply their changes through the incident state machine
and reach agents and sentinel-executor through ``DomainMessages``.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sentinel.core.config.workflow import IncidentSettings
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import ExecutorAction, KafkaTopic, RequestKind, WorkflowRequest
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.state import incident_rules as rules
from sentinel.workflow.discord import DiscordWebhook
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.routing import DomainWorkflow, required_record
from sentinel.workflow.sre.incidents.alertmanager import AlertmanagerClient
from sentinel.workflow.sre.incidents.investigation import Investigation
from sentinel.workflow.sre.incidents.manual_actions import ManualActions
from sentinel.workflow.sre.incidents.repository import IncidentRepository
from sentinel.workflow.sre.incidents.submission import FixSubmission


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
        self.submission = FixSubmission(settings, incidents, messages)
        self.manual_actions = ManualActions(settings, incidents, messages)
        self.investigation = Investigation(
            settings, incidents, knowledge, alertmanager=alertmanager, messages=messages, submission=self.submission
        )
        workflow_timeout = timedelta(seconds=settings.incident.workflow_timeout_seconds)
        super().__init__(
            AgentDomain.SRE,
            incidents,
            messages,
            topics={
                KafkaTopic.CLUSTER_ALERTS: self.investigation.on_cluster_alert,
                KafkaTopic.SRE_RETURNS: self.investigation.on_agent_return,
            },
            requests={
                RequestKind.INCIDENT: self.investigation.on_request,
                RequestKind.MANUAL_ACTION: self.manual_actions.on_request,
                RequestKind.IGNORE: self._on_ignore,
            },
            executor_returns={
                ExecutorAction.CREATE_PULL_REQUEST: self.submission.on_executor_return,
                ExecutorAction.RUN_COMMAND: self.manual_actions.on_executor_return,
            },
            active=rules.ACTIVE,
            timed_out=rules.workflow_timed_out,
            workflow_timeout=workflow_timeout,
        )

    def expire_workflows(self) -> None:
        super().expire_workflows()
        now = datetime.now(UTC)
        self.manual_actions.expire_actions(now)

    def _on_ignore(self, request: WorkflowRequest) -> None:
        incident_id = required_record(request)
        self.incidents.ignore_incident(incident_id)
