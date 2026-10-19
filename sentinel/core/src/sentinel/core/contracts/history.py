from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field

AGENT_HISTORY_LIMIT = 5


class PriorAttempt(BaseModel):
    number: int
    trigger: str
    status: str
    started_at: str
    prompt: str = ""
    head_sha: str = ""
    result: dict[str, Any] = Field(default_factory=dict)


def prior_attempts(attempts: Sequence[Mapping[str, Any]]) -> list[PriorAttempt]:
    finished = [attempt for attempt in attempts if attempt["finished_at"] is not None]
    recent = finished[-AGENT_HISTORY_LIMIT:]
    return [PriorAttempt.model_validate(attempt) for attempt in recent]
