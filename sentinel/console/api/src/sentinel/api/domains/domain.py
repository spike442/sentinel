from abc import ABC
from importlib.metadata import version

from fastapi import APIRouter, Request
from sentinel.api.domains.contract import DomainKind, DomainManifest
from sentinel.api.domains.workflow import RecordWorkflow, workflow_router
from sentinel.core.domain import AgentDomain
from sentinel.core.errors import NotFound


class ConsoleDomain(ABC):
    """A console domain served under ``/api/<domain>``: its workflows, each run by its own agent, and its events.

    One switch enables the domain and every agent it manages; ``events`` adds the domain's external triggers under
    ``/api/<domain>/events/``.
    """

    id: str
    label: str
    icon: str
    switch: AgentDomain
    workflows: tuple[RecordWorkflow, ...]

    def enabled(self, request: Request) -> bool:
        return self.switch in request.app.state.settings.agents

    def require_enabled(self, request: Request) -> None:
        if not self.enabled(request):
            raise NotFound(f"{self.id} is not enabled")

    def events(self) -> APIRouter | None:
        return None


def domain_router(domain: ConsoleDomain) -> APIRouter:
    router = APIRouter(prefix=f"/{domain.id}", tags=[domain.id])

    @router.get("/manifest")
    def manifest(request: Request) -> DomainManifest:
        live = domain.enabled(request)
        agents = [workflow.agent for workflow in domain.workflows]
        consuming = request.app.state.liveness.consuming(agents) if live else set()
        workflows = [workflow.summary(request, consuming) for workflow in domain.workflows] if live else []
        running = live and all(workflow.running for workflow in workflows)
        active = sum(workflow.active for workflow in workflows)
        release = version("sentinel-core")
        return DomainManifest(
            id=domain.id,
            label=domain.label,
            icon=domain.icon,
            kind=DomainKind.WORKFLOW,
            version=release,
            enabled=live,
            running=running,
            active=active,
            workflows=workflows,
        )

    for workflow in domain.workflows:
        workflow_routes = workflow_router(workflow, domain.require_enabled)
        router.include_router(workflow_routes)
    events = domain.events()
    if events is not None:
        router.include_router(events, prefix="/events")
    return router
