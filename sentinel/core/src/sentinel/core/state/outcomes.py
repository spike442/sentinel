from dataclasses import dataclass
from typing import Any

from sentinel.core.errors import Conflict, NotFound


@dataclass(frozen=True)
class Accepted[State]:
    state: State
    value: Any = None


@dataclass(frozen=True)
class Unchanged:
    value: Any = None


@dataclass(frozen=True)
class Rejected:
    reason: str


@dataclass(frozen=True)
class Missing:
    pass


@dataclass(frozen=True)
class Removed:
    pass


type Outcome[State] = Accepted[State] | Unchanged | Rejected | Missing | Removed


def succeeded(outcome: Outcome[Any]) -> bool:
    return isinstance(outcome, Accepted | Unchanged)


def require_existing(outcome: Outcome[Any], missing_message: str) -> None:
    if isinstance(outcome, Missing):
        raise NotFound(missing_message)


def require_allowed(outcome: Outcome[Any]) -> None:
    if isinstance(outcome, Rejected):
        raise Conflict(outcome.reason)


def require_transition(outcome: Outcome[Any], missing_message: str) -> None:
    require_existing(outcome, missing_message)
    require_allowed(outcome)
