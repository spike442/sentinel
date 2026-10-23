"""Pure incident state machine.

Every incident change is a pure function ``(Incident | None, event, now) -> Outcome``. Functions
never mutate their inputs and perform no I/O; the repository locks the row, builds an immutable
snapshot, calls ``transition``, and persists the returned state. The ``TRANSITIONS`` table is the
complete list of what may happen to an incident; anything missing from it cannot happen.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sentinel.core.domain import ActionStatus, DiagnosisStatus, IncidentEvent, IncidentStatus
from sentinel.core.state import history
from sentinel.core.state import incident_rules as rules
from sentinel.core.state.incident_rules import approval_id
from sentinel.core.state.outcomes import Accepted, Missing, Rejected, Removed, Unchanged
from sentinel.core.state.outcomes import Outcome as GenericOutcome
from sentinel.core.state.workflows import INCIDENT_FLOW, allows
from sentinel.workflow.sre.incidents.events import (
    AgentResultSaved,
    AlertFired,
    AlertResolved,
    Deleted,
    Event,
    FixReviewed,
    Ignored,
    ManualActionClaimed,
    ManualActionExpired,
    ManualActionRecorded,
    ReplayRequested,
    RunSkipped,
    RunStarted,
    WorkflowFailed,
)
from sentinel.workflow.sre.incidents.snapshot import Incident, JsonObject

Outcome = GenericOutcome[Incident]


def with_event(state: Incident, event: str, now: datetime, prompt: str = "") -> Incident:
    timeline = history.with_event(state.timeline, event, now, prompt=prompt)
    return replace(state, timeline=timeline)


def _source(alert: JsonObject) -> str:
    labels = alert.get("labels", {})
    return labels.get("source", "")


def _owned(state: Incident, workflow_id: str) -> bool:
    return state.workflow_id == workflow_id


def alert_fired(state: Incident, event: AlertFired, now: datetime) -> Outcome:
    if state.status in rules.STOPPED or state.status == IncidentStatus.IGNORED.value:
        return Rejected(f"cluster alerts do not requeue {state.status} incidents")
    reopened = state.status in rules.REOPENABLE
    if state.workflow_id and not reopened:
        return Unchanged()
    source = _source(event.alert)
    queued = replace(
        state,
        workflow_id=event.workflow_id,
        status=IncidentStatus.REOPENED.value if reopened else IncidentStatus.ACKNOWLEDGED.value,
        alert=event.alert,
        source=source,
        repository=event.repository,
        diagnosis={"status": DiagnosisStatus.OBSERVED.value, "evidence": [], "validation": []},
        updated_at=now,
    )
    timeline_event = IncidentEvent.REOPENED if reopened else IncidentEvent.ACKNOWLEDGED
    acknowledged = with_event(queued, timeline_event, now)
    return Accepted(acknowledged, event.workflow_id)


def alert_resolved(state: Incident, event: AlertResolved, now: datetime) -> Outcome:
    source = _source(event.alert)
    attempts = history.interrupted(state.attempts, IncidentStatus.RESOLVED.value, now)
    resolved = replace(
        state,
        status=IncidentStatus.RESOLVED.value,
        alert=event.alert,
        source=source,
        repository=event.repository,
        attempts=attempts,
        updated_at=now,
    )
    if state.status != IncidentStatus.RESOLVED.value:
        resolved = with_event(resolved, IncidentEvent.RESOLVED, now)
    return Accepted(resolved)


def replay_requested(state: Incident, event: ReplayRequested, now: datetime) -> Outcome:
    if _owned(state, event.workflow_id):
        return Unchanged()
    if state.status not in rules.REPLAYABLE:
        return Rejected(f"incident cannot be replayed from {state.status}")
    replayed = replace(state, workflow_id=event.workflow_id, updated_at=now)
    replayed = with_event(replayed, IncidentEvent.REPLAYED, now)
    return Accepted(replayed)


def run_started(state: Incident, event: RunStarted, now: datetime) -> Outcome:
    owned = _owned(state, event.workflow_id)
    if state.closed or not owned:
        return Rejected("incident is not owned by this workflow or is no longer processable")
    own_attempt = history.latest(state.attempts, event.workflow_id)
    if own_attempt is not None:
        return Unchanged()
    superseded = history.interrupted(state.attempts, history.SUPERSEDED, now)
    attempts = history.started(superseded, event.trigger, event.workflow_id, event.prompt, now)
    started = replace(state, status=IncidentStatus.RUNNING.value, attempts=attempts, updated_at=now)
    if event.trigger == "replay":
        started = replace(started, replayed_at=now)
    started = with_event(started, IncidentEvent.RUNNING, now, event.prompt)
    return Accepted(started)


def run_skipped(state: Incident, event: RunSkipped, now: datetime) -> Outcome:
    owned = _owned(state, event.workflow_id)
    if not owned or state.status not in rules.QUEUED:
        return Rejected("incident is not queued for this workflow")
    hypothesis = "The alert stopped firing before the investigation started, so no investigation ran."
    diagnosis = {**state.diagnosis, "hypothesis": hypothesis}
    skipped = replace(state, status=IncidentStatus.SKIPPED.value, diagnosis=diagnosis, updated_at=now)
    skipped = with_event(skipped, IncidentEvent.SKIPPED, now)
    return Accepted(skipped)


def workflow_failed(state: Incident, event: WorkflowFailed, now: datetime) -> Outcome:
    owned = _owned(state, event.workflow_id)
    if state.closed or not owned:
        return Rejected("incident is not owned by this workflow or cannot fail")
    diagnosis = {**state.diagnosis, "hypothesis": f"The workflow failed: {event.error}."}
    error = {"error": event.error}
    attempts = history.recorded(
        state.attempts,
        event.workflow_id,
        IncidentStatus.FAILED.value,
        now,
        result=error,
        audit_actions=event.audit_actions,
        tool_budget=event.tool_budget,
    )
    failed = replace(
        state,
        status=IncidentStatus.FAILED.value,
        diagnosis=diagnosis,
        attempts=attempts,
        tool_budget=event.tool_budget or state.tool_budget,
        updated_at=now,
    )
    if state.status != IncidentStatus.FAILED.value:
        failed = with_event(failed, IncidentEvent.FAILED, now)
    return Accepted(failed)


def agent_result_saved(state: Incident, event: AgentResultSaved, now: datetime) -> Outcome:
    owned = _owned(state, event.workflow_id)
    if not owned or state.status != IncidentStatus.RUNNING.value:
        return Rejected("incident is not running for this workflow")
    result = event.result
    diagnosis = result["diagnosis"]
    updated = state
    if state.status != result["status"]:
        updated = with_event(updated, result["status"], now)
        updated = replace(updated, status=result["status"])
    attempt_result = {"diagnosis": diagnosis, "pull_request_url": result["pull_request_url"]}
    attempts = history.recorded(
        state.attempts,
        event.workflow_id,
        result["status"],
        now,
        result=attempt_result,
        audit_actions=result["audit_actions"],
        tool_budget=result["tool_budget"],
    )
    saved = replace(
        updated,
        diagnosis=diagnosis,
        pull_request_url=result["pull_request_url"],
        attempts=attempts,
        tool_budget=result["tool_budget"],
        updated_at=now,
    )
    return Accepted(saved)


def manual_action_claimed(state: Incident, event: ManualActionClaimed, now: datetime) -> Outcome:
    if state.closed:
        return Rejected("incident is no longer actionable")
    request = event.request
    actions = state.diagnosis.get("manual_actions", [])
    index = request["action_index"]
    if index < 0 or index >= len(actions):
        return Rejected("manual action is no longer approved")
    current_approval = approval_id(state.diagnosis, index)
    if current_approval != request["approval_id"] or actions[index] != request["action"]:
        return Rejected("manual action approval has changed")
    previous = [action for action in state.manual_actions if action["approval_id"] == request["approval_id"]]
    if any(action["status"] == ActionStatus.SUCCEEDED.value for action in previous):
        return Rejected("manual action already succeeded")
    running = [action for action in previous if rules.action_running(action, now, event.timeout_seconds)]
    if running:
        return Rejected("manual action is already running")
    claimed_at = now.isoformat()
    claim = {
        "workflow_id": request["workflow_id"],
        "approval_id": request["approval_id"],
        "action_index": index,
        "status": ActionStatus.RUNNING.value,
        "at": claimed_at,
        "claim_at": claimed_at,
    }
    kept = [
        action
        for action in state.manual_actions
        if action["workflow_id"] != request["workflow_id"]
        and not (action["approval_id"] == request["approval_id"] and action["status"] == ActionStatus.RUNNING.value)
    ]
    manual_actions = (*kept, claim)
    claimed = replace(state, manual_actions=manual_actions, updated_at=now)
    return Accepted(claimed, claimed_at)


def manual_action_recorded(state: Incident, event: ManualActionRecorded, now: datetime) -> Outcome:
    result = event.result

    def claimed_by_result(action: JsonObject) -> bool:
        return action["workflow_id"] == result["workflow_id"] and action["claim_at"] == result["claim_at"]

    claims = [action for action in state.manual_actions if claimed_by_result(action)]
    if any(action["status"] != ActionStatus.RUNNING.value for action in claims):
        return Unchanged()
    if not any(action["status"] == ActionStatus.RUNNING.value for action in claims):
        return Rejected("manual action was not claimed")
    recorded_entry = {**result, "at": now.isoformat()}
    manual_actions = tuple(recorded_entry if claimed_by_result(action) else action for action in state.manual_actions)
    recorded = replace(state, manual_actions=manual_actions, updated_at=now)
    if result["status"] == ActionStatus.SUCCEEDED.value and state.status == IncidentStatus.BLOCKED.value:
        recorded = replace(recorded, status=IncidentStatus.AWAITING.value)
    recorded = with_event(recorded, IncidentEvent.MANUAL_ACTION_EXECUTED, now)
    return Accepted(recorded)


def manual_action_expired(state: Incident, event: ManualActionExpired, now: datetime) -> Outcome:
    def matches(action: JsonObject) -> bool:
        return action["workflow_id"] == event.workflow_id and action["claim_at"] == event.claim_at

    claims = [action for action in state.manual_actions if matches(action)]
    if not any(action["status"] == ActionStatus.RUNNING.value for action in claims):
        return Unchanged()
    timed_out = {"status": ActionStatus.FAILED.value, "error": "ActionTimedOut", "at": now.isoformat()}
    manual_actions = tuple({**action, **timed_out} if matches(action) else action for action in state.manual_actions)
    expired = replace(state, manual_actions=manual_actions, updated_at=now)
    expired = with_event(expired, IncidentEvent.MANUAL_ACTION_EXECUTED, now)
    return Accepted(expired)


def fix_reviewed(state: Incident, event: FixReviewed, now: datetime) -> Outcome:
    linked = replace(state, review_id=event.review_id, updated_at=now)
    timeline = history.with_event(linked.timeline, f"fix_review_{event.status}", now, reason=event.reason)
    reviewed = replace(linked, timeline=timeline)
    return Accepted(reviewed)


def ignored(state: Incident, _event: Ignored, now: datetime) -> Outcome:
    if state.status == IncidentStatus.IGNORED.value:
        return Unchanged()
    attempts = history.interrupted(state.attempts, IncidentStatus.IGNORED.value, now)
    ignored_state = replace(state, status=IncidentStatus.IGNORED.value, attempts=attempts, updated_at=now)
    ignored_state = with_event(ignored_state, IncidentEvent.IGNORED, now)
    return Accepted(ignored_state)


def deleted(_state: Incident, _event: Deleted, _now: datetime) -> Outcome:
    return Removed()


TRANSITIONS: Mapping[type, Callable[[Incident, Any, datetime], Outcome]] = MappingProxyType(
    {
        AlertFired: alert_fired,
        AlertResolved: alert_resolved,
        ReplayRequested: replay_requested,
        RunStarted: run_started,
        RunSkipped: run_skipped,
        WorkflowFailed: workflow_failed,
        AgentResultSaved: agent_result_saved,
        ManualActionClaimed: manual_action_claimed,
        ManualActionRecorded: manual_action_recorded,
        ManualActionExpired: manual_action_expired,
        FixReviewed: fix_reviewed,
        Ignored: ignored,
        Deleted: deleted,
    }
)


def transition(state: Incident | None, event: Event, now: datetime) -> Outcome:
    if state is None:
        return Missing()
    event_type = type(event)
    decide = TRANSITIONS[event_type]
    outcome = decide(state, event, now)
    if isinstance(outcome, Accepted):
        target = outcome.state.status
        if not allows(INCIDENT_FLOW, state.status, event_type.__name__, target):
            return Rejected(f"{event_type.__name__} cannot move an incident from {state.status} to {target}")
    return outcome
