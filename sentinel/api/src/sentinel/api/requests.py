import asyncio
from uuid import uuid4

from sentinel.api.config import ApiSettings
from sentinel.core.config.common import CommonSettings
from sentinel.core.contracts.incidents import (
    AlertmanagerNotification,
    IncidentRequest,
    ManualAction,
    ManualActionRequest,
)
from sentinel.core.contracts.reviews import configured_repository
from sentinel.core.domain import AgentDomain
from sentinel.core.errors import Conflict, NotFound
from sentinel.core.kafka.contracts import KafkaTopic, RequestKind, WorkflowRequest
from sentinel.core.kafka.producer import publish
from sentinel.core.persistence.queries import IncidentReader, PrReviewReader
from sentinel.core.state import incident_rules, review_rules


async def publish_request(
    settings: CommonSettings, domain: AgentDomain, kind: RequestKind, workflow_id: str, payload: dict
) -> None:
    request = WorkflowRequest(domain=domain, kind=kind, workflow_id=workflow_id, payload=payload)
    await asyncio.to_thread(publish, settings, KafkaTopic.WORKFLOW_REQUESTS, workflow_id, request)


async def forward_cluster_alerts(settings: CommonSettings, notification: AlertmanagerNotification) -> None:
    for alert in notification.alerts:
        labels = {"source": "alertmanager", **alert.labels}
        sourced = alert.model_copy(update={"labels": labels})
        await asyncio.to_thread(publish, settings, KafkaTopic.CLUSTER_ALERTS, alert.fingerprint, sourced)


class IncidentWorkflowRequests:
    def __init__(self, incidents: IncidentReader, settings: CommonSettings):
        self.incidents = incidents
        self.settings = settings

    async def replay_incident(self, incident_id: str, prompt: str) -> str:
        incident = await self._incident(incident_id)
        if incident["status"] not in incident_rules.REPLAYABLE:
            raise Conflict(f"incident cannot be replayed from {incident['status']}")
        workflow_id = f"sre-replay-{uuid4()}"
        request = IncidentRequest(kind="replay", incident_id=incident_id, prompt=prompt)
        payload = request.model_dump(mode="json")
        await publish_request(self.settings, AgentDomain.SRE, RequestKind.INCIDENT, workflow_id, payload)
        return workflow_id

    async def execute_manual_action(self, incident_id: str, action_index: int) -> str:
        incident = await self._incident(incident_id)
        diagnosis = incident["diagnosis"]
        actions = diagnosis.get("manual_actions", [])
        if action_index < 0 or action_index >= len(actions):
            raise NotFound("manual action not found")
        approval_id = incident_rules.approval_id(diagnosis, action_index)
        workflow_id = f"manual-action-{incident_id}-{approval_id}-{uuid4().hex}"
        action = ManualAction.model_validate(actions[action_index])
        request = ManualActionRequest(
            incident_id=incident_id, action_index=action_index, approval_id=approval_id, action=action
        )
        payload = request.model_dump(mode="json")
        await publish_request(self.settings, AgentDomain.SRE, RequestKind.MANUAL_ACTION, workflow_id, payload)
        return workflow_id

    async def ignore_incident(self, incident_id: str) -> str:
        return await self._request_change(incident_id, RequestKind.IGNORE, "sre-ignore")

    async def delete_incident(self, incident_id: str) -> str:
        return await self._request_change(incident_id, RequestKind.DELETE, "sre-delete")

    async def _request_change(self, incident_id: str, kind: RequestKind, prefix: str) -> str:
        await self._incident(incident_id)
        workflow_id = f"{prefix}-{uuid4()}"
        payload = {"incident_id": incident_id}
        await publish_request(self.settings, AgentDomain.SRE, kind, workflow_id, payload)
        return workflow_id

    async def _incident(self, incident_id: str) -> dict:
        incident = await asyncio.to_thread(self.incidents.get, incident_id)
        if incident is None:
            raise NotFound(f"incident not found: {incident_id}")
        return incident


class PrReviewWorkflowRequests:
    def __init__(self, settings: ApiSettings, reviews: PrReviewReader):
        self.settings = settings
        self.reviews = reviews

    async def check_reviews(self) -> str:
        workflow_id = f"pr-review-poll-{uuid4()}"
        await publish_request(self.settings, AgentDomain.PULL_REQUEST_REVIEW, RequestKind.DISCOVER, workflow_id, {})
        return workflow_id

    async def replay_review(self, review_id: str, prompt: str) -> str:
        review = await self._configured_review(review_id, review_rules.REPLAYABLE, "replayed")
        workflow_id = f"pr-review-replay-{uuid4()}"
        payload = {"review_id": review["id"], "prompt": prompt}
        await publish_request(self.settings, AgentDomain.PULL_REQUEST_REVIEW, RequestKind.REPLAY, workflow_id, payload)
        return workflow_id

    async def fix_review(self, review_id: str, prompt: str) -> str:
        review = await self._configured_review(review_id, review_rules.FIXABLE, "fixed")
        workflow_id = f"pr-review-fix-{uuid4()}"
        payload = {"review_id": review["id"], "prompt": prompt}
        await publish_request(self.settings, AgentDomain.PULL_REQUEST_REVIEW, RequestKind.FIX, workflow_id, payload)
        return workflow_id

    async def delete_review(self, review_id: str) -> str:
        await self._review(review_id)
        workflow_id = f"pr-review-delete-{uuid4()}"
        payload = {"review_id": review_id}
        await publish_request(self.settings, AgentDomain.PULL_REQUEST_REVIEW, RequestKind.DELETE, workflow_id, payload)
        return workflow_id

    async def _configured_review(self, review_id: str, statuses: frozenset[str], verb: str) -> dict:
        review = await self._review(review_id)
        if review["status"] not in statuses:
            raise Conflict(f"A {review['status']} review cannot be {verb}")
        repository = configured_repository(self.settings.repositories, review["repository"], review["owner"])
        if repository is None:
            raise Conflict("The review repository is no longer configured")
        return review

    async def _review(self, review_id: str) -> dict:
        review = await asyncio.to_thread(self.reviews.get, review_id)
        if review is None:
            raise NotFound(f"review not found: {review_id}")
        return review
