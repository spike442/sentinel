from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from sentinel.core.persistence.postgres import PostgresDatabase, apply_event
from sentinel.core.state.outcomes import Accepted


class TransitionRepository(ABC):
    """Apply events to rows of ``model``; ``new_values`` gives a missing row's columns when an event creates it.

    ``on_terminal`` runs after the commit whenever an event moves a row into one of the ``terminal`` statuses.
    """

    database: PostgresDatabase
    model: type
    state_type: type
    decide: Callable[..., Any]
    terminal: frozenset[str]
    on_terminal: Callable[[str], None] | None = None

    @abstractmethod
    def new_values(self, source: Any) -> dict[str, Any]:
        pass

    def apply_transition(self, entity_id: str, event: Any, create_from: Any = None) -> Any:
        initial = None if create_from is None else self.new_values(create_from)
        entered = []

        def decide(state: Any, decided_event: Any, now: Any) -> Any:
            outcome = self.decide(state, decided_event, now)
            moved = isinstance(outcome, Accepted) and state is not None and outcome.state.status != state.status
            if moved and outcome.state.status in self.terminal:
                entered.append(outcome.state.status)
            return outcome

        outcome = apply_event(
            self.database,
            model=self.model,
            state_type=self.state_type,
            transition=decide,
            entity_id=entity_id,
            event=event,
            initial_values=initial,
        )
        if entered and self.on_terminal is not None:
            self.on_terminal(entity_id)
        return outcome
