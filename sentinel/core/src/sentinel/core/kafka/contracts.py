from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sentinel.core.domain import AgentDomain
from sentinel.core.errors import SentinelError
from sentinel.core.observability.audit import AuditAction, ToolBudget


class KafkaTopic(StrEnum):
    CLUSTER_ALERTS = "cluster_alerts"
    WORKFLOW_REQUESTS = "workflow_requests"

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


class RequestKind(StrEnum):
    INCIDENT = "incident"
    PR_REVIEW = "review"
    DISCOVER = "discover"
    REPLAY = "replay"
    FIX = "fix"
    MANUAL_ACTION = "manual-action"
    IGNORE = "ignore"
    DELETE = "delete"


class RecordMessage(BaseModel):
    """A message about one incident or review record, named by ``record_id``, within one workflow run.

    Every message the workflow consumes besides a cluster alert carries both ids, so a message whose handling
    fails marks its record failed without knowing the domain's payload.
    """

    workflow_id: str
    record_id: str | None = None


RECORD_TOPICS = frozenset(
    {
        KafkaTopic.WORKFLOW_REQUESTS,
        KafkaTopic.SRE_RETURNS,
        KafkaTopic.PR_REVIEW_RETURNS,
        KafkaTopic.EXECUTOR_RETURNS,
    }
)


class RunFailure(BaseModel):
    error: str
    audit_actions: list[AuditAction] = Field(default_factory=list)
    tool_budget: ToolBudget | None = None


class WorkflowRequest(RecordMessage):
    domain: AgentDomain
    kind: RequestKind
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentCommand(RecordMessage):
    record_id: str
    kind: RequestKind
    payload: dict[str, Any]


class AgentReturn(RecordMessage):
    record_id: str
    kind: RequestKind
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    failure: RunFailure | None = None

    @model_validator(mode="after")
    def carries_a_result_or_a_failure(self) -> "AgentReturn":
        if (self.result is None) == (self.failure is None):
            raise ValueError("an agent return carries either a result or a failure")
        return self


class ExecutorAction(StrEnum):
    CREATE_PULL_REQUEST = "create-pull-request"
    MERGE_PULL_REQUEST = "merge-pull-request"
    PUSH_FIX = "push-fix"
    RUN_COMMAND = "run-command"


class ExecutorEnvelope(RecordMessage):
    record_id: str
    action: ExecutorAction
    domain: AgentDomain
    context: dict[str, Any] = Field(default_factory=dict)


class ExecutorCommand(ExecutorEnvelope):
    payload: dict[str, Any]


class ExecutorReturn(ExecutorEnvelope):
    result: dict[str, Any] | None = None
    error: str | None = None
