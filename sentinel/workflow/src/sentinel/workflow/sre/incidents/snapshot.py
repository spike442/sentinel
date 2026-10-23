from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sentinel.core.state import incident_rules as rules

JsonObject = Mapping[str, Any]


@dataclass(frozen=True)
class Incident:
    status: str
    workflow_id: str | None
    updated_at: datetime
    repository: str
    source: str = ""
    alert: JsonObject = field(default_factory=dict)
    diagnosis: JsonObject = field(default_factory=dict)
    pull_request_url: str | None = None
    review_id: str | None = None
    replayed_at: datetime | None = None
    manual_actions: tuple[JsonObject, ...] = ()
    timeline: tuple[JsonObject, ...] = ()
    attempts: tuple[JsonObject, ...] = ()
    tool_budget: JsonObject = field(default_factory=dict)

    @property
    def closed(self) -> bool:
        return self.status in rules.CLOSED
