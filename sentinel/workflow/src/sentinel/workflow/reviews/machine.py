"""Pure pull-request review state machine.

One record holds every review of a pull request: each run (a new revision, an operator replay, or an operator's
fix) opens an attempt in ``attempts`` and the record's columns show the latest one. ``TRANSITIONS`` lists
everything that may happen to a review.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sentinel.core.domain import PrReviewStatus, ReviewTrigger
from sentinel.core.state import history
from sentinel.core.state import review_rules as rules
from sentinel.core.state.outcomes import Accepted, Missing, Rejected, Removed, Unchanged
from sentinel.core.state.outcomes import Outcome as GenericOutcome
from sentinel.core.state.workflows import PR_REVIEW_FLOW, allows
from sentinel.workflow.reviews.events import (
    Acknowledged,
    Deleted,
    Event,
    FixClaimed,
    FixDeclined,
    FixProposed,
    FixPushed,
    Merged,
    PrReviewClaimed,
    PrReviewFailed,
    ReplayRejected,
    ResultSaved,
)
from sentinel.workflow.reviews.snapshot import JsonObject, PrReview

Outcome = GenericOutcome[PrReview]


def with_event(state: PrReview, event: str, now: datetime, **details: Any) -> PrReview:
    timeline = history.with_event(state.timeline, event, now, **details)
    return replace(state, timeline=timeline)


def fix_result(proposal: JsonObject) -> dict[str, Any]:
    fix = proposal["fix"]
    return {
        "summary": fix["summary"],
        "commit_message": fix["commit_message"],
        "changes": fix["changes"],
        "checks": proposal["checks"],
    }


def _owned(state: PrReview, workflow_id: str) -> bool:
    return state.workflow_id == workflow_id


def _active_for(state: PrReview, workflow_id: str) -> bool:
    owned = _owned(state, workflow_id)
    return owned and state.status in rules.ACTIVE


def _fixing_for(state: PrReview, workflow_id: str) -> bool:
    owned = _owned(state, workflow_id)
    return owned and state.status == PrReviewStatus.FIXING.value


def acknowledged(_state: PrReview, _event: Acknowledged, _now: datetime) -> Outcome:
    return Unchanged()


def review_claimed(state: PrReview, event: PrReviewClaimed, now: datetime) -> Outcome:
    if state.status not in rules.CLAIMABLE_BY_NEW_WORKFLOW:
        return Rejected(f"review is {state.status}")
    own_attempt = history.latest(state.attempts, event.workflow_id)
    if _owned(state, event.workflow_id) and own_attempt is not None:
        return Unchanged()
    superseded = history.interrupted(state.attempts, history.SUPERSEDED, now)
    attempts = history.started(
        superseded,
        event.trigger,
        event.workflow_id,
        event.prompt,
        now,
        base_sha=event.base_sha,
        head_sha=event.head_sha,
    )
    claimed = replace(
        state,
        workflow_id=event.workflow_id,
        status=PrReviewStatus.RUNNING.value,
        base_sha=event.base_sha,
        head_sha=event.head_sha,
        checks=(),
        risk=None,
        confidence=None,
        summary="",
        findings=(),
        merge=None,
        decision_reason="",
        reviewed_at=None,
        attempts=attempts,
        tool_budget={},
        updated_at=now,
    )
    claimed = with_event(
        claimed, PrReviewStatus.RUNNING, now, trigger=event.trigger, prompt=event.prompt, head_sha=event.head_sha
    )
    return Accepted(claimed)


def review_failed(state: PrReview, event: PrReviewFailed, now: datetime) -> Outcome:
    active = _active_for(state, event.workflow_id)
    if not active:
        return Rejected("review is not running for this workflow")
    reason = f"PR review workflow failed: {event.error}."
    error = {"error": event.error}
    attempts = history.recorded(
        state.attempts,
        event.workflow_id,
        PrReviewStatus.FAILED.value,
        now,
        result=error,
        audit_actions=event.audit_actions,
        tool_budget=event.tool_budget,
    )
    failed = replace(
        state,
        status=PrReviewStatus.FAILED.value,
        summary=reason,
        decision_reason=reason,
        attempts=attempts,
        tool_budget=event.tool_budget or state.tool_budget,
        updated_at=now,
    )
    failed = with_event(failed, PrReviewStatus.FAILED, now, reason=reason)
    return Accepted(failed)


def result_saved(state: PrReview, event: ResultSaved, now: datetime) -> Outcome:
    owned = _owned(state, event.workflow_id)
    if not owned or state.status != PrReviewStatus.RUNNING.value:
        return Rejected("review is not running for this workflow")
    result = event.result
    model_review, decision = result["review"], result["decision"]
    status = PrReviewStatus.RUNNING.value if decision["merge"] else PrReviewStatus.BLOCKED.value
    review_result = {
        "checks": result["checks"],
        "risk": model_review["risk"],
        "confidence": model_review["confidence"],
        "summary": model_review["summary"],
        "findings": model_review["findings"],
        "merge": decision["merge"],
        "decision_reason": decision["reason"],
    }
    checks = tuple(result["checks"])
    findings = tuple(model_review["findings"])
    attempts = history.recorded(
        state.attempts,
        event.workflow_id,
        status,
        now,
        result=review_result,
        audit_actions=result["audit_actions"],
        tool_budget=result["tool_budget"],
    )
    decided = replace(
        state,
        status=status,
        checks=checks,
        risk=model_review["risk"],
        confidence=model_review["confidence"],
        summary=model_review["summary"],
        findings=findings,
        merge=decision["merge"],
        decision_reason=decision["reason"],
        reviewed_at=now,
        attempts=attempts,
        tool_budget=result["tool_budget"],
        updated_at=now,
    )
    if status == PrReviewStatus.BLOCKED.value:
        decided = with_event(decided, status, now, reason=decision["reason"])
    return Accepted(decided)


def merged(state: PrReview, event: Merged, now: datetime) -> Outcome:
    if state.status == PrReviewStatus.MERGED.value:
        return Unchanged()
    attempts = history.interrupted(state.attempts, PrReviewStatus.MERGED.value, now)
    merged_state = replace(
        state,
        status=PrReviewStatus.MERGED.value,
        merge=True,
        merged_at=now,
        merge_commit_sha=event.sha,
        attempts=attempts,
        updated_at=now,
    )
    merged_state = with_event(merged_state, PrReviewStatus.MERGED, now, sha=event.sha)
    return Accepted(merged_state)


def replay_rejected(state: PrReview, event: ReplayRejected, now: datetime) -> Outcome:
    if state.status not in rules.REPLAYABLE:
        return Rejected(f"a {state.status} review cannot be replayed")
    attempts = history.interrupted(state.attempts, PrReviewStatus.FAILED.value, now)
    rejected = replace(
        state,
        status=PrReviewStatus.FAILED.value,
        summary=event.reason,
        decision_reason=event.reason,
        attempts=attempts,
        updated_at=now,
    )
    rejected = with_event(rejected, PrReviewStatus.FAILED, now, reason=event.reason)
    return Accepted(rejected)


def fix_claimed(state: PrReview, event: FixClaimed, now: datetime) -> Outcome:
    fixing = _fixing_for(state, event.workflow_id)
    if fixing:
        return Unchanged()
    if state.status not in rules.FIXABLE:
        return Rejected(f"only blocked reviews can be fixed, not {state.status}")
    attempts = history.started(
        state.attempts,
        ReviewTrigger.FIX,
        event.workflow_id,
        event.prompt,
        now,
        base_sha=state.base_sha,
        head_sha=state.head_sha,
    )
    claimed = replace(
        state, workflow_id=event.workflow_id, status=PrReviewStatus.FIXING.value, attempts=attempts, updated_at=now
    )
    claimed = with_event(claimed, PrReviewStatus.FIXING, now, prompt=event.prompt, head_sha=state.head_sha)
    return Accepted(claimed)


def fix_declined(state: PrReview, event: FixDeclined, now: datetime) -> Outcome:
    if not event.workflow_id:
        if state.status not in rules.FIXABLE:
            return Rejected(f"only blocked reviews can be fixed, not {state.status}")
        declined = with_event(state, "fix_declined", now, reason=event.reason)
        return Accepted(declined)
    fixing = _fixing_for(state, event.workflow_id)
    if not fixing:
        return Rejected("review is not fixing for this workflow")
    proposed = {} if event.proposal is None else fix_result(event.proposal)
    reason = {"reason": event.reason}
    audit_actions = () if event.proposal is None else event.proposal["audit_actions"]
    tool_budget = None if event.proposal is None else event.proposal["tool_budget"]
    attempts = history.recorded(
        state.attempts,
        event.workflow_id,
        PrReviewStatus.BLOCKED.value,
        now,
        result={**proposed, **reason},
        audit_actions=audit_actions,
        tool_budget=tool_budget,
    )
    decision_reason = f"Fix declined: {event.reason}"
    declined = replace(
        state,
        status=PrReviewStatus.BLOCKED.value,
        decision_reason=decision_reason,
        attempts=attempts,
        updated_at=now,
    )
    declined = with_event(declined, PrReviewStatus.BLOCKED, now, reason=decision_reason)
    return Accepted(declined)


def fix_proposed(state: PrReview, event: FixProposed, now: datetime) -> Outcome:
    fixing = _fixing_for(state, event.workflow_id)
    if not fixing:
        return Rejected("review is not fixing for this workflow")
    proposal = event.proposal
    proposed = fix_result(proposal)
    attempts = history.recorded(
        state.attempts,
        event.workflow_id,
        history.RUNNING,
        now,
        result=proposed,
        audit_actions=proposal["audit_actions"],
        tool_budget=proposal["tool_budget"],
    )
    saved = replace(state, attempts=attempts, tool_budget=proposal["tool_budget"], updated_at=now)
    return Accepted(saved)


def fix_pushed(state: PrReview, event: FixPushed, now: datetime) -> Outcome:
    fixing = _fixing_for(state, event.workflow_id)
    if not fixing:
        return Rejected("review is not fixing for this workflow")
    pushed = {"commit_sha": event.sha}
    attempts = history.recorded(state.attempts, event.workflow_id, rules.FIX_PUSHED, now, result=pushed)
    acknowledged_fix = replace(
        state, status=PrReviewStatus.ACKNOWLEDGED.value, head_sha=event.sha, attempts=attempts, updated_at=now
    )
    acknowledged_fix = with_event(acknowledged_fix, PrReviewStatus.ACKNOWLEDGED, now, head_sha=event.sha)
    return Accepted(acknowledged_fix)


def deleted(_state: PrReview, _event: Deleted, _now: datetime) -> Outcome:
    return Removed()


TRANSITIONS: Mapping[type, Callable[[PrReview, Any, datetime], Outcome]] = MappingProxyType(
    {
        Acknowledged: acknowledged,
        PrReviewClaimed: review_claimed,
        PrReviewFailed: review_failed,
        ResultSaved: result_saved,
        Merged: merged,
        ReplayRejected: replay_rejected,
        FixClaimed: fix_claimed,
        FixDeclined: fix_declined,
        FixProposed: fix_proposed,
        FixPushed: fix_pushed,
        Deleted: deleted,
    }
)


def transition(state: PrReview | None, event: Event, now: datetime) -> Outcome:
    if state is None:
        return Missing()
    event_type = type(event)
    decide = TRANSITIONS[event_type]
    outcome = decide(state, event, now)
    if isinstance(outcome, Accepted):
        target = outcome.state.status
        if not allows(PR_REVIEW_FLOW, state.status, event_type.__name__, target):
            return Rejected(f"{event_type.__name__} cannot move a review from {state.status} to {target}")
    return outcome
