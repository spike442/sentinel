from fastapi import HTTPException, Request
from sentinel.core.domain import AgentDomain
from sentinel.core.persistence.queries import IncidentReader, PrReviewReader

READERS = {AgentDomain.SRE: IncidentReader, AgentDomain.PULL_REQUEST_REVIEW: PrReviewReader}


def require_enabled(request: Request, domain: AgentDomain) -> None:
    if domain not in request.app.state.settings.agents:
        raise HTTPException(status_code=503, detail=f"{domain} is disabled")


def enabled_reader(request: Request, domain: AgentDomain) -> IncidentReader | PrReviewReader:
    require_enabled(request, domain)
    reader = READERS[domain]
    return reader(request.app.state.database)
