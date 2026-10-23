import json
import logging
from typing import Any
from uuid import uuid4

import httpx
from sentinel.core.config.workflow import IncidentSettings
from sentinel.core.contracts.history import prior_attempts
from sentinel.core.contracts.incidents import Alert, IncidentRequest, IncidentResult, PreparedIncident
from sentinel.core.contracts.knowledge import KnowledgeSearchRequest, RetrievedContext
from sentinel.core.domain import AgentDomain, AlertStatus
from sentinel.core.errors import NotFound
from sentinel.core.kafka.contracts import AgentReturn, WorkflowRequest
from sentinel.core.knowledge import KnowledgeClient
from sentinel.core.observability.metrics import cluster_alerts_processed
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.sre.incidents.alertmanager import AlertmanagerClient
from sentinel.workflow.sre.incidents.repository import IncidentRepository
from sentinel.workflow.sre.incidents.submission import FixSubmission

logger = logging.getLogger(__name__)


def knowledge_query(prompt: str, alert: Alert) -> str:
    alert_fields = alert.model_dump(mode="json")
    alert_json = json.dumps(alert_fields, sort_keys=True)
    return f"{prompt}\n{alert_json}" if prompt else alert_json


class Investigation:
    def __init__(
        self,
        settings: IncidentSettings,
        incidents: IncidentRepository,
        knowledge: KnowledgeClient,
        *,
        alertmanager: AlertmanagerClient,
        messages: DomainMessages,
        submission: FixSubmission,
    ):
        self.repository = settings.incident.repository
        self.repository_config = settings.incident_repository
        self.incidents = incidents
        self.knowledge = knowledge
        self.alertmanager = alertmanager
        self.messages = messages
        self.submission = submission

    def on_cluster_alert(self, payload: dict[str, Any]) -> None:
        try:
            alert = Alert.model_validate(payload)
            self.handle_cluster_alert(alert)
        except Exception:
            cluster_alerts_processed.labels(result="error").inc()
            raise
        cluster_alerts_processed.labels(result="ok").inc()

    def handle_cluster_alert(self, alert: Alert) -> None:
        if alert.status is AlertStatus.RESOLVED:
            self.incidents.resolve_alert(alert.fingerprint, alert, self.repository)
            return
        candidate_id = f"sre-{uuid4()}"
        workflow_id = self.incidents.queue_alert(alert.fingerprint, alert, candidate_id, self.repository)
        if workflow_id is None:
            return
        firing = self.still_firing(alert)
        if not firing:
            logger.info("incident run skipped incident_id=%s reason=alert_not_firing", alert.fingerprint)
            self.incidents.skip_run(alert.fingerprint, workflow_id)
            return
        request = IncidentRequest(kind="alert", incident_id=alert.fingerprint, alert=alert)
        try:
            self.start_investigation(request, workflow_id)
        except Exception as error:
            error_type = type(error).__name__
            self.messages.fail(alert.fingerprint, workflow_id, error_type)
            raise

    def still_firing(self, alert: Alert) -> bool:
        try:
            firing = self.alertmanager.is_firing(alert)
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("alert state unknown incident_id=%s error=%s", alert.fingerprint, error_type)
            return True
        return firing

    def on_request(self, message: WorkflowRequest) -> None:
        request = IncidentRequest.model_validate(message.payload)
        self.start_investigation(request, message.workflow_id)

    def on_agent_return(self, payload: dict[str, Any]) -> None:
        agent_return = AgentReturn.model_validate(payload)
        incident_id = agent_return.record_id
        workflow_id = agent_return.workflow_id
        if agent_return.failure is not None:
            self.messages.fail(incident_id, workflow_id, agent_return.failure)
            return
        result = IncidentResult.model_validate(agent_return.result)
        self.submission.submit_fix(incident_id, result, workflow_id)

    def start_investigation(self, request: IncidentRequest, workflow_id: str) -> None:
        prepared = self.prepare_incident(request, workflow_id)
        if prepared is not None:
            self.messages.command_agent(request.incident_id, workflow_id, prepared)

    def prepare_incident(self, request: IncidentRequest, workflow_id: str) -> PreparedIncident | None:
        replay = request.kind == "replay"
        if replay:
            replaying = self.incidents.request_replay(request.incident_id, workflow_id)
            if not replaying:
                return None
        stored = self._load_incident(request.incident_id) if replay else None
        prompt = request.prompt if replay else ""
        started = self.incidents.start_run(request.incident_id, workflow_id, request.kind, prompt)
        if not started:
            return None
        alert = request.alert or Alert.model_validate(stored["alert"])
        query = knowledge_query(request.prompt, alert)
        rag_context = self._search_knowledge(query)
        history = prior_attempts(stored["attempts"]) if stored else []
        request_fields = request.model_dump(exclude={"alert"})
        return PreparedIncident(
            **request_fields,
            alert=alert,
            repository=self.repository_config,
            rag_context=rag_context,
            history=history,
        )

    def _load_incident(self, incident_id: str) -> dict:
        incident = self.incidents.get(incident_id)
        if incident is None:
            raise NotFound(f"incident not found: {incident_id}")
        return incident

    def _search_knowledge(self, query: str) -> list[RetrievedContext]:
        search = KnowledgeSearchRequest(domain=AgentDomain.SRE, repository=self.repository, query=query)
        return self.knowledge.search(search)
