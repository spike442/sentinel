from collections.abc import Callable
from copy import deepcopy
from dataclasses import fields
from datetime import datetime
from typing import Any

from sentinel.core.state.outcomes import Accepted, Outcome, Removed
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


CONNECT_TIMEOUT_SECONDS = 10
LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "30s"


class PostgresDatabase:
    def __init__(self, database_dsn: str):
        self.engine = create_engine(
            database_dsn,
            connect_args={
                "connect_timeout": CONNECT_TIMEOUT_SECONDS,
                "options": f"-c lock_timeout={LOCK_TIMEOUT} -c statement_timeout={STATEMENT_TIMEOUT}",
            },
            pool_pre_ping=True,
        )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def close(self) -> None:
        self.engine.dispose()


def database_now(session: Session) -> datetime:
    statement = select(func.now())
    return session.scalar(statement)


def load_for_update[Record: Base](
    session: Session, model: type[Record], entity_id: str, initial_values: dict[str, Any] | None
) -> Record | None:
    if initial_values is not None:
        statement = (
            insert(model)
            .values(entity_id=entity_id, updated_at=func.now(), **initial_values)
            .on_conflict_do_nothing(index_elements=["entity_id"])
        )
        session.execute(statement)
    return session.get(model, entity_id, with_for_update=True, populate_existing=True)


def snapshot[State](record: Base, state_type: type[State]) -> State:
    values = {}
    for item in fields(state_type):  # type: ignore[arg-type]
        column = getattr(record, item.name)
        value = deepcopy(column)
        values[item.name] = tuple(value) if isinstance(value, list) else value
    return state_type(**values)


def write(record: Base, state: Any) -> None:
    for item in fields(state):
        value = getattr(state, item.name)
        value = list(value) if isinstance(value, tuple) else value
        current = getattr(record, item.name)
        if current != value:
            copied = deepcopy(value)
            setattr(record, item.name, copied)


def apply_event[State, Event](
    database: PostgresDatabase,
    *,
    model: type[Base],
    state_type: type[State],
    transition: Callable[[State | None, Event, datetime], Outcome[State]],
    entity_id: str,
    event: Event,
    initial_values: dict[str, Any] | None = None,
) -> Outcome[State]:
    with database.sessions.begin() as session:
        record = load_for_update(session, model, entity_id, initial_values)
        state = None if record is None else snapshot(record, state_type)
        now = database_now(session)
        outcome = transition(state, event, now)
        if isinstance(outcome, Accepted):
            write(record, outcome.state)
        elif isinstance(outcome, Removed):
            session.delete(record)
        return outcome
