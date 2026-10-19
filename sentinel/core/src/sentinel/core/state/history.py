"""Record history shared by every domain: a timeline of status events and one entry per agent attempt.

Both are append-only and never trimmed. A replay or a fix starts a new attempt; earlier attempts keep their prompt,
result, audit trail, and tool budget, so the current record columns are only the latest view of its history.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

JsonObject = Mapping[str, Any]
RUNNING = "running"
SUPERSEDED = "superseded"


def with_event(timeline: Sequence[JsonObject], event: str, now: datetime, **details: Any) -> tuple[JsonObject, ...]:
    recorded = {key: value for key, value in details.items() if value not in (None, "")}
    entry = {"at": now.isoformat(), "event": str(event), **recorded}
    return (*timeline, entry)


def started(
    attempts: Sequence[JsonObject], trigger: str, workflow_id: str, prompt: str, now: datetime, **revision: Any
) -> tuple[JsonObject, ...]:
    attempt = {
        "number": len(attempts) + 1,
        "trigger": str(trigger),
        "workflow_id": workflow_id,
        "prompt": prompt,
        "status": RUNNING,
        "started_at": now.isoformat(),
        "finished_at": None,
        **revision,
        "result": {},
        "audit_actions": [],
        "tool_budget": {},
    }
    return (*attempts, attempt)


def recorded(
    attempts: Sequence[JsonObject],
    workflow_id: str,
    status: str,
    now: datetime,
    *,
    result: JsonObject | None = None,
    audit_actions: Sequence[JsonObject] = (),
    tool_budget: JsonObject | None = None,
) -> tuple[JsonObject, ...]:
    index = _latest_index(attempts, workflow_id)
    if index is None:
        return tuple(attempts)
    attempt = attempts[index]
    finished_at = None if status == RUNNING else now.isoformat()
    merged_result = {**attempt["result"], **(result or {})}
    updated = {
        **attempt,
        "status": status,
        "finished_at": finished_at,
        "result": merged_result,
        "audit_actions": [*attempt["audit_actions"], *audit_actions],
        "tool_budget": tool_budget or attempt["tool_budget"],
    }
    return (*attempts[:index], updated, *attempts[index + 1 :])


def interrupted(attempts: Sequence[JsonObject], status: str, now: datetime) -> tuple[JsonObject, ...]:
    return tuple(
        {**attempt, "status": status, "finished_at": now.isoformat()} if attempt["status"] == RUNNING else attempt
        for attempt in attempts
    )


def latest(attempts: Sequence[JsonObject], workflow_id: str) -> JsonObject | None:
    index = _latest_index(attempts, workflow_id)
    return None if index is None else attempts[index]


def _latest_index(attempts: Sequence[JsonObject], workflow_id: str) -> int | None:
    for index in range(len(attempts) - 1, -1, -1):
        if attempts[index]["workflow_id"] == workflow_id:
            return index
    return None
