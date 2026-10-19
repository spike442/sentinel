from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sentinel.api.requests import IncidentWorkflowRequests, forward_cluster_alerts
from sentinel.api.routes.enabled import enabled_reader
from sentinel.core.contracts.incidents import AlertmanagerNotification
from sentinel.core.domain import AgentDomain
from sentinel.core.errors import NotFound
from sentinel.core.persistence.queries import IncidentReader

router = APIRouter(tags=["sre"])


class ReplayRequest(BaseModel):
    prompt: str = ""


class ManualActionRequest(BaseModel):
    action_index: int


def _repository(request: Request) -> IncidentReader:
    return enabled_reader(request, AgentDomain.SRE)


def _requests(request: Request) -> IncidentWorkflowRequests:
    incidents = _repository(request)
    return IncidentWorkflowRequests(incidents, request.app.state.settings)


@router.get("/incidents")
def incidents(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(default=None),
) -> dict:
    return {"incidents": _repository(request).list(limit, status)}


@router.get("/incidents/{incident_id}")
def incident(incident_id: str, request: Request) -> dict:
    found = _repository(request).get(incident_id)
    if found is None:
        raise NotFound(f"incident not found: {incident_id}")
    return found


@router.post("/incidents/replay/{incident_id}", status_code=202)
async def replay_incident(
    incident_id: str,
    request: Request,
    replay: ReplayRequest,
) -> dict[str, str]:
    prompt = replay.prompt.strip()
    workflow_id = await _requests(request).replay_incident(incident_id, prompt)
    return {"status": "accepted", "workflow_id": workflow_id}


@router.post("/incidents/{incident_id}/ignore", status_code=202)
async def ignore_incident(
    incident_id: str,
    request: Request,
) -> dict[str, str]:
    workflow_id = await _requests(request).ignore_incident(incident_id)
    return {"status": "accepted", "workflow_id": workflow_id}


@router.post("/incidents/{incident_id}/manual-actions/execute", status_code=202)
async def execute_manual_action(
    incident_id: str,
    request: Request,
    action: ManualActionRequest,
) -> dict[str, str]:
    workflow_id = await _requests(request).execute_manual_action(incident_id, action.action_index)
    return {"status": "accepted", "action_index": str(action.action_index), "workflow_id": workflow_id}


@router.delete("/incidents/{incident_id}", status_code=202)
async def delete_incident(
    incident_id: str,
    request: Request,
) -> dict[str, str]:
    workflow_id = await _requests(request).delete_incident(incident_id)
    return {"status": "accepted", "workflow_id": workflow_id}


@router.post("/events/alertmanager", status_code=202)
async def alertmanager_notification(notification: AlertmanagerNotification, request: Request) -> dict[str, str]:
    """Alertmanager's webhook receiver posts here; a non-2xx reply makes it retry the notification.

    Alerts are published even while SRE is disabled: the cluster alert topic holds them until the
    incident workflow is enabled again and consumes them from its committed offset.
    """
    await forward_cluster_alerts(request.app.state.settings, notification)
    return {"status": "accepted"}
