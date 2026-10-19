from dataclasses import dataclass

from sentinel.workflow.reviews.snapshot import JsonObject


@dataclass(frozen=True)
class Acknowledged:
    pass


@dataclass(frozen=True)
class PrReviewClaimed:
    workflow_id: str
    trigger: str
    prompt: str
    base_sha: str
    head_sha: str


@dataclass(frozen=True)
class PrReviewFailed:
    workflow_id: str
    error: str
    audit_actions: tuple[JsonObject, ...] = ()
    tool_budget: JsonObject | None = None


@dataclass(frozen=True)
class ResultSaved:
    workflow_id: str
    result: JsonObject


@dataclass(frozen=True)
class Merged:
    sha: str


@dataclass(frozen=True)
class ReplayRejected:
    reason: str


@dataclass(frozen=True)
class FixClaimed:
    workflow_id: str
    prompt: str


@dataclass(frozen=True)
class FixDeclined:
    reason: str
    workflow_id: str = ""
    proposal: JsonObject | None = None


@dataclass(frozen=True)
class FixProposed:
    workflow_id: str
    proposal: JsonObject


@dataclass(frozen=True)
class FixPushed:
    workflow_id: str
    sha: str


@dataclass(frozen=True)
class Deleted:
    pass


Event = (
    Acknowledged
    | PrReviewClaimed
    | PrReviewFailed
    | ResultSaved
    | Merged
    | ReplayRejected
    | FixClaimed
    | FixDeclined
    | FixProposed
    | FixPushed
    | Deleted
)
