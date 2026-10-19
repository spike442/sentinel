from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

JsonObject = Mapping[str, Any]


@dataclass(frozen=True)
class PrReview:
    status: str
    workflow_id: str | None
    updated_at: datetime
    base_sha: str = ""
    head_sha: str = ""
    checks: tuple[JsonObject, ...] = ()
    risk: str | None = None
    confidence: str | None = None
    summary: str = ""
    findings: tuple[str, ...] = ()
    merge: bool | None = None
    decision_reason: str = ""
    reviewed_at: datetime | None = None
    merged_at: datetime | None = None
    merge_commit_sha: str = ""
    timeline: tuple[JsonObject, ...] = ()
    attempts: tuple[JsonObject, ...] = ()
    tool_budget: JsonObject = field(default_factory=dict)
