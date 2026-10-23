from fastapi import APIRouter, Depends, Request
from sentinel.api.domains.contract import Accepted
from sentinel.api.domains.domain import ConsoleDomain
from sentinel.api.domains.sre.incidents import IncidentWorkflow
from sentinel.api.domains.sre.reviews import ReviewWorkflow
from sentinel.api.requests import PrReviewWorkflowRequests, forward_cluster_alerts
from sentinel.core.contracts.incidents import AlertmanagerNotification
from sentinel.core.domain import AgentDomain


class SreDomain(ConsoleDomain):
    id = AgentDomain.SRE.value
    label = "SRE"
    icon = "kubernetes"
    switch = AgentDomain.SRE

    def __init__(self) -> None:
        self.incidents = IncidentWorkflow()
        self.reviews = ReviewWorkflow()
        self.workflows = (self.incidents, self.reviews)

    def events(self) -> APIRouter:
        router = APIRouter()

        @router.post("/alertmanager", status_code=202)
        async def alertmanager(notification: AlertmanagerNotification, request: Request) -> dict[str, str]:
            """Alertmanager's webhook receiver posts here; a non-2xx reply makes it retry the notification.

            Alerts are published even while SRE is disabled: the cluster alert topic holds them until the
            incident workflow is enabled again and consumes them from its committed offset.
            """
            await forward_cluster_alerts(request.app.state.settings, notification)
            return {"status": "accepted"}

        @router.post("/check", status_code=202, dependencies=[Depends(self.require_enabled)])
        async def check(request: Request) -> Accepted:
            reader = self.reviews.reader(request)
            requests = PrReviewWorkflowRequests(request.app.state.settings, reader)
            workflow_id = await requests.check_reviews()
            return Accepted(workflow_id=workflow_id)

        return router
