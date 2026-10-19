from datetime import datetime, timedelta

from sentinel.core.domain import PrReviewStatus

FINAL = frozenset({PrReviewStatus.BLOCKED.value, PrReviewStatus.MERGED.value})
NOTIFIED = FINAL | {PrReviewStatus.FAILED.value}
REVISABLE = frozenset({PrReviewStatus.BLOCKED.value, PrReviewStatus.FAILED.value})
ACTIVE = frozenset({PrReviewStatus.RUNNING.value, PrReviewStatus.FIXING.value})
REPLAYABLE = REVISABLE | ACTIVE
FIXABLE = frozenset({PrReviewStatus.BLOCKED.value})
CLAIMABLE_BY_NEW_WORKFLOW = REPLAYABLE | {PrReviewStatus.ACKNOWLEDGED.value}
FIX_PUSHED = "pushed"


def needs_review(status: str | None, revision: tuple[str, str], reviewed: tuple[str, str]) -> bool:
    if status is None or status == PrReviewStatus.ACKNOWLEDGED.value:
        return True
    return status in REVISABLE and revision != reviewed


def workflow_timed_out(status: str, updated_at: datetime, now: datetime, timeout: timedelta) -> bool:
    return status in ACTIVE and updated_at < now - timeout
