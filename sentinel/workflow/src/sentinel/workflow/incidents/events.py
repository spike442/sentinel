from dataclasses import dataclass

from sentinel.workflow.incidents.snapshot import JsonObject


@dataclass(frozen=True)
class AlertFired:
    alert: JsonObject
    workflow_id: str
    repository: str


@dataclass(frozen=True)
class AlertResolved:
    alert: JsonObject
    repository: str


@dataclass(frozen=True)
class ReplayRequested:
    workflow_id: str


@dataclass(frozen=True)
class RunStarted:
    workflow_id: str
    trigger: str
    prompt: str = ""


@dataclass(frozen=True)
class RunSkipped:
    workflow_id: str


@dataclass(frozen=True)
class WorkflowFailed:
    workflow_id: str
    error: str


@dataclass(frozen=True)
class AgentResultSaved:
    workflow_id: str
    result: JsonObject


@dataclass(frozen=True)
class ManualActionClaimed:
    request: JsonObject
    timeout_seconds: int


@dataclass(frozen=True)
class ManualActionRecorded:
    result: JsonObject


@dataclass(frozen=True)
class ManualActionExpired:
    workflow_id: str
    claim_at: str


@dataclass(frozen=True)
class Ignored:
    pass


@dataclass(frozen=True)
class Deleted:
    pass


Event = (
    AlertFired
    | AlertResolved
    | ReplayRequested
    | RunStarted
    | RunSkipped
    | WorkflowFailed
    | AgentResultSaved
    | ManualActionClaimed
    | ManualActionRecorded
    | ManualActionExpired
    | Ignored
    | Deleted
)
