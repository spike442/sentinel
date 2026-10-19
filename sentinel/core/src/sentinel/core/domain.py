from enum import StrEnum

from pydantic import BaseModel


class AgentDomain(StrEnum):
    SRE = "sre"
    PULL_REQUEST_REVIEW = "pr-review"


class AuditStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IncidentStatus(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    REOPENED = "reopened"
    RUNNING = "running"
    AWAITING = "awaiting"
    BLOCKED = "blocked"
    FAILED = "failed"
    IGNORED = "ignored"
    RESOLVED = "resolved"
    SKIPPED = "skipped"


class DiagnosisStatus(StrEnum):
    OBSERVED = "observed"
    PROPOSED = "proposed"
    BLOCKED = "blocked"


class IncidentEvent(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    REOPENED = "reopened"
    REPLAYED = "replayed"
    RUNNING = "running"
    FAILED = "failed"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    MANUAL_ACTION_EXECUTED = "manual_action_executed"
    SKIPPED = "skipped"


class ActionStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AlertStatus(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"


class PrReviewStatus(StrEnum):
    """Where a review's workflow is; ``blocked`` is a reviewed revision the policy does not merge.

    ``fixing`` is an operator-approved fix of a blocked review being written and pushed to the pull request.
    """

    ACKNOWLEDGED = "acknowledged"
    RUNNING = "running"
    BLOCKED = "blocked"
    FIXING = "fixing"
    FAILED = "failed"
    MERGED = "merged"


class ReviewTrigger(StrEnum):
    REVIEW = "review"
    REPLAY = "replay"
    FIX = "fix"


class RepositoryIdentity(BaseModel):
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}.git"
