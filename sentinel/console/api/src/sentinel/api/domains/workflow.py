from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sentinel.api.domains.contract import (
    OPEN_TONES,
    Accepted,
    ActionRequest,
    RecordAction,
    RecordLink,
    Tone,
    WorkflowState,
    WorkflowSummary,
    WorkflowTransition,
    WorkflowView,
)
from sentinel.core.domain import AgentDomain
from sentinel.core.errors import Conflict, NotFound
from sentinel.core.persistence.queries import RecordReader
from sentinel.core.state.workflows import Flow

RECORD_LIMIT = 500


class RecordWorkflow(ABC):
    """One workflow of a console domain, served under ``/api/<domain>/<workflow>``, and the agent that runs it.

    The workflow names its statuses, transition graph, and state tones; it titles a record, lists the actions its
    current status allows (the pure rules decide), links related records, and runs an action. Every action is
    checked against that list first.
    """

    id: str
    label: str
    agent: AgentDomain
    statuses: type[StrEnum]
    flow: Flow
    tones: Mapping[str, Tone]
    reader_type: type[RecordReader]

    @abstractmethod
    def title(self, record: dict[str, Any]) -> str:
        pass

    @abstractmethod
    def actions(self, record: dict[str, Any]) -> list[RecordAction]:
        pass

    @abstractmethod
    async def run_action(self, request: Request, record: dict[str, Any], name: str, body: ActionRequest) -> str:
        pass

    def links(self, record: dict[str, Any]) -> list[RecordLink]:
        return []

    def reader(self, request: Request) -> RecordReader:
        return self.reader_type(request.app.state.database)

    def view(self, record: dict[str, Any]) -> dict[str, Any]:
        title = self.title(record)
        actions = self.actions(record)
        listed = [action.model_dump() for action in actions]
        links = self.links(record)
        linked = [link.model_dump() for link in links]
        return {**record, "title": title, "actions": listed, "links": linked}

    def summary(self, request: Request, consuming: set[AgentDomain]) -> WorkflowSummary:
        reader = self.reader(request)
        counts = reader.status_counts()
        active = sum(count for status, count in counts.items() if self.tones.get(status) in OPEN_TONES)
        running = self.agent in consuming
        return WorkflowSummary(id=self.id, label=self.label, agent=self.agent.value, running=running, active=active)


def workflow_router(spec: RecordWorkflow, require_enabled: Callable[[Request], None]) -> APIRouter:
    router = APIRouter(prefix=f"/{spec.id}", dependencies=[Depends(require_enabled)])

    def found(request: Request, record_id: str) -> dict[str, Any]:
        reader = spec.reader(request)
        record = reader.get(record_id)
        if record is None:
            raise NotFound(f"{spec.label} record not found: {record_id}")
        return record

    @router.get("/workflow")
    def workflow() -> WorkflowView:
        states = [
            WorkflowState(name=status.value, tone=spec.tones.get(status.value, Tone.WAITING))
            for status in spec.statuses
        ]
        transitions = [
            WorkflowTransition(source=source, event=event, target=target) for source, event, target in spec.flow
        ]
        tones = dict(spec.tones)
        return WorkflowView(domain=spec.id, states=states, transitions=transitions, tones=tones)

    @router.get("/records")
    def records(
        request: Request,
        limit: int = Query(default=200, ge=1, le=RECORD_LIMIT),
        status: str | None = Query(default=None),
    ) -> dict[str, list[dict[str, Any]]]:
        reader = spec.reader(request)
        listed = reader.list(limit, status)
        views = [spec.view(record) for record in listed]
        return {"records": views}

    @router.get("/records/{record_id}")
    def record(record_id: str, request: Request) -> dict[str, Any]:
        current = found(request, record_id)
        return spec.view(current)

    @router.post("/records/{record_id}/actions/{action}", status_code=202)
    async def run_action(record_id: str, action: str, request: Request, body: ActionRequest) -> Accepted:
        current = found(request, record_id)
        allowed = {item.name for item in spec.actions(current)}
        if action not in allowed:
            raise Conflict(f"{action} is not available for a {current['status']} {spec.label.lower()} record")
        workflow_id = await spec.run_action(request, current, action, body)
        return Accepted(workflow_id=workflow_id)

    return router
