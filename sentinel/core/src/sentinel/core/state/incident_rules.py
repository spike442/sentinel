from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from sentinel.core.digest import json_digest
from sentinel.core.domain import ActionStatus, IncidentStatus

QUEUED = frozenset({IncidentStatus.ACKNOWLEDGED.value, IncidentStatus.REOPENED.value})
ACTIVE = QUEUED | {IncidentStatus.RUNNING.value}
STOPPED = frozenset({IncidentStatus.AWAITING.value, IncidentStatus.BLOCKED.value, IncidentStatus.FAILED.value})
REOPENABLE = frozenset({IncidentStatus.RESOLVED.value, IncidentStatus.SKIPPED.value})
REPLAYABLE = ACTIVE | STOPPED | {IncidentStatus.SKIPPED.value}
CLOSED = frozenset({IncidentStatus.IGNORED.value, IncidentStatus.RESOLVED.value})
NOTIFIED = STOPPED | {IncidentStatus.RESOLVED.value}


def workflow_timed_out(status: str, updated_at: datetime, now: datetime, timeout: timedelta) -> bool:
    return status in ACTIVE and updated_at < now - timeout


def _lease_expired(action: Mapping[str, Any], now: datetime, timeout_seconds: int) -> bool:
    lease = timedelta(seconds=timeout_seconds)
    started_at = datetime.fromisoformat(action["at"])
    return started_at < now - lease


def action_timed_out(action: Mapping[str, Any], now: datetime, timeout_seconds: int) -> bool:
    expired = _lease_expired(action, now, timeout_seconds)
    return action["status"] == ActionStatus.RUNNING.value and expired


def action_running(action: Mapping[str, Any], now: datetime, timeout_seconds: int) -> bool:
    expired = _lease_expired(action, now, timeout_seconds)
    return action["status"] == ActionStatus.RUNNING.value and not expired


def approval_id(diagnosis: Mapping[str, Any], action_index: int) -> str:
    return json_digest([diagnosis, action_index])
