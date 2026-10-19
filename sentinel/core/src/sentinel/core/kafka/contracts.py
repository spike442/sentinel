from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sentinel.core.domain import AgentDomain
from sentinel.core.errors import SentinelError


class KafkaTopic(StrEnum):
    CLUSTER_ALERTS = "cluster_alerts"
    WORKFLOW_REQUESTS = "workflow_requests"
    OUTCOMES = "outcomes"

    SRE_COMMANDS = "sre_commands"
    SRE_RETURNS = "sre_returns"
    PR_REVIEW_COMMANDS = "pr_review_commands"
    PR_REVIEW_RETURNS = "pr_review_returns"

    EXECUTOR_COMMANDS = "executor_commands"
    EXECUTOR_RETURNS = "executor_returns"


class InvalidMessageError(ValueError):
    pass


UNDELIVERABLE = (InvalidMessageError, ValidationError, SentinelError)


@dataclass(frozen=True)
class KafkaMessage:
    topic: KafkaTopic
    payload: dict[str, Any]
    published_at: datetime
    commit: Callable[[], None] = field(compare=False)


class WorkflowOutcome(BaseModel):
    domain: AgentDomain
    workflow_id: str
    record: dict[str, Any]


class RequestKind(StrEnum):
    INCIDENT = "incident"
    PR_REVIEW = "review"
    DISCOVER = "discover"
    REPLAY = "replay"
    FIX = "fix"
    MANUAL_ACTION = "manual-action"
    IGNORE = "ignore"
    DELETE = "delete"


class WorkflowRequest(BaseModel):
    domain: AgentDomain
    kind: RequestKind
    workflow_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentCommand(BaseModel):
    kind: RequestKind
    workflow_id: str
    payload: dict[str, Any]


class AgentReturn(BaseModel):
    kind: RequestKind
    workflow_id: str
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class ExecutorAction(StrEnum):
    CREATE_PULL_REQUEST = "create-pull-request"
    MERGE_PULL_REQUEST = "merge-pull-request"
    PUSH_FIX = "push-fix"
    RUN_COMMAND = "run-command"


class ExecutorEnvelope(BaseModel):
    action: ExecutorAction
    domain: AgentDomain
    workflow_id: str
    context: dict[str, Any]


class ExecutorCommand(ExecutorEnvelope):
    payload: dict[str, Any]


class ExecutorReturn(ExecutorEnvelope):
    result: dict[str, Any] | None = None
    error: str | None = None
