"""Workflow graphs: every status change each state machine may make, also drawn by the UI.

Each machine's ``transition`` rejects an accepted outcome whose status change is not listed here, so the
graph is the enforced contract. An outcome that keeps its status is not a change and is not listed.
"""

from collections.abc import Sequence

from sentinel.core.domain import IncidentStatus, PrReviewStatus

Flow = tuple[tuple[str | None, str, str], ...]

Incident = IncidentStatus
INCIDENT_FLOW: Flow = (
    (None, "AlertFired", Incident.ACKNOWLEDGED.value),
    (Incident.RESOLVED.value, "AlertFired", Incident.REOPENED.value),
    (Incident.SKIPPED.value, "AlertFired", Incident.REOPENED.value),
    (Incident.ACKNOWLEDGED.value, "RunStarted", Incident.RUNNING.value),
    (Incident.REOPENED.value, "RunStarted", Incident.RUNNING.value),
    (Incident.BLOCKED.value, "RunStarted", Incident.RUNNING.value),
    (Incident.FAILED.value, "RunStarted", Incident.RUNNING.value),
    (Incident.AWAITING.value, "RunStarted", Incident.RUNNING.value),
    (Incident.SKIPPED.value, "RunStarted", Incident.RUNNING.value),
    (Incident.ACKNOWLEDGED.value, "RunSkipped", Incident.SKIPPED.value),
    (Incident.REOPENED.value, "RunSkipped", Incident.SKIPPED.value),
    (Incident.ACKNOWLEDGED.value, "WorkflowFailed", Incident.FAILED.value),
    (Incident.REOPENED.value, "WorkflowFailed", Incident.FAILED.value),
    (Incident.RUNNING.value, "WorkflowFailed", Incident.FAILED.value),
    (Incident.AWAITING.value, "WorkflowFailed", Incident.FAILED.value),
    (Incident.BLOCKED.value, "WorkflowFailed", Incident.FAILED.value),
    (Incident.SKIPPED.value, "WorkflowFailed", Incident.FAILED.value),
    (Incident.RUNNING.value, "AgentResultSaved", Incident.BLOCKED.value),
    (Incident.RUNNING.value, "AgentResultSaved", Incident.FAILED.value),
    (Incident.RUNNING.value, "AgentResultSaved", Incident.AWAITING.value),
    (Incident.BLOCKED.value, "ManualActionRecorded", Incident.AWAITING.value),
    ("*", "AlertResolved", Incident.RESOLVED.value),
    ("*", "Ignored", Incident.IGNORED.value),
)

Review = PrReviewStatus
PR_REVIEW_FLOW: Flow = (
    (None, "Acknowledged", Review.ACKNOWLEDGED.value),
    (Review.ACKNOWLEDGED.value, "PrReviewClaimed", Review.RUNNING.value),
    (Review.BLOCKED.value, "PrReviewClaimed", Review.RUNNING.value),
    (Review.FAILED.value, "PrReviewClaimed", Review.RUNNING.value),
    (Review.FIXING.value, "PrReviewClaimed", Review.RUNNING.value),
    (Review.RUNNING.value, "ResultSaved", Review.BLOCKED.value),
    (Review.RUNNING.value, "PrReviewFailed", Review.FAILED.value),
    (Review.FIXING.value, "PrReviewFailed", Review.FAILED.value),
    (Review.RUNNING.value, "ReplayRejected", Review.FAILED.value),
    (Review.BLOCKED.value, "ReplayRejected", Review.FAILED.value),
    (Review.FIXING.value, "ReplayRejected", Review.FAILED.value),
    (Review.BLOCKED.value, "FixClaimed", Review.FIXING.value),
    (Review.FIXING.value, "FixDeclined", Review.BLOCKED.value),
    (Review.FIXING.value, "FixPushed", Review.ACKNOWLEDGED.value),
    ("*", "Merged", Review.MERGED.value),
)


def allows(flow: Sequence[tuple[str | None, str, str]], source: str, event: str, target: str) -> bool:
    if source == target:
        return True
    return (source, event, target) in flow or ("*", event, target) in flow
