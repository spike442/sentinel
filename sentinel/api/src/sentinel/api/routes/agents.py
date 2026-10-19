from fastapi import APIRouter, Request
from sentinel.core.domain import AgentDomain, IncidentStatus, PrReviewStatus
from sentinel.core.errors import NotFound
from sentinel.core.state.workflows import INCIDENT_FLOW, PR_REVIEW_FLOW

router = APIRouter(prefix="/agents", tags=["agents"])

WORKFLOWS = {
    AgentDomain.SRE: (IncidentStatus, INCIDENT_FLOW),
    AgentDomain.PULL_REQUEST_REVIEW: (PrReviewStatus, PR_REVIEW_FLOW),
}


@router.get("")
def list_agents(request: Request) -> dict[str, list[dict]]:
    enabled = request.app.state.settings.agents
    running = request.app.state.liveness.consuming(enabled)
    agents = [
        {"domain": domain.value, "enabled": domain in enabled, "running": domain in running} for domain in AgentDomain
    ]
    return {"agents": agents}


@router.get("/{domain}/workflow")
def workflow(domain: AgentDomain, request: Request) -> dict:
    if domain not in request.app.state.settings.agents:
        raise NotFound(f"agent is not enabled: {domain.value}")
    statuses, flow = WORKFLOWS[domain]
    states = [status.value for status in statuses]
    transitions = [{"source": source, "event": event, "target": target} for source, event, target in flow]
    return {"domain": domain.value, "states": states, "transitions": transitions}
