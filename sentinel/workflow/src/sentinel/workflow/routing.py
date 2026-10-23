import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import (
    RECORD_TOPICS,
    UNDELIVERABLE,
    ExecutorAction,
    ExecutorReturn,
    InvalidMessageError,
    KafkaMessage,
    KafkaTopic,
    RecordMessage,
    RequestKind,
    WorkflowRequest,
)
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.repository import DomainRecords

logger = logging.getLogger(__name__)

Handler = Callable[[KafkaMessage], None]
PayloadHandler = Callable[[dict[str, Any]], None]
TimedOut = Callable[[str, datetime, datetime, timedelta], bool]
SHARED_TOPICS = (KafkaTopic.WORKFLOW_REQUESTS, KafkaTopic.EXECUTOR_RETURNS)
EXPIRY_BATCH = 500


class DomainWorkflow:
    """Dispatch one domain's messages by topic; shared topics then dispatch by request kind or executor action.

    A message whose handling fails marks the record it names failed; nothing retries it, and an operator replays
    the record from the UI. Every domain also deletes records on request and fails the runs that pass
    ``workflow_timeout`` in one of its ``active`` statuses.
    """

    def __init__(
        self,
        domain: AgentDomain,
        records: DomainRecords,
        messages: DomainMessages,
        *,
        topics: Mapping[KafkaTopic, PayloadHandler],
        requests: Mapping[RequestKind, Callable[[WorkflowRequest], None]],
        executor_returns: Mapping[ExecutorAction, Callable[[ExecutorReturn], None]],
        active: frozenset[str],
        timed_out: TimedOut,
        workflow_timeout: timedelta,
    ):
        self.domain = domain
        self.records = records
        self.messages = messages
        self.topics: dict[KafkaTopic, PayloadHandler] = {
            **topics,
            KafkaTopic.WORKFLOW_REQUESTS: self._on_request,
            KafkaTopic.EXECUTOR_RETURNS: self._on_executor_return,
        }
        self.requests = {**requests, RequestKind.DELETE: self._on_delete}
        self.executor_returns = executor_returns
        self.active = active
        self.timed_out = timed_out
        self.workflow_timeout = workflow_timeout

    def route_message(self, message: KafkaMessage) -> None:
        route = self.topics.get(message.topic)
        if route is None:
            raise InvalidMessageError(f"unsupported {self.domain} topic: {message.topic}")
        try:
            route(message.payload)
        except UNDELIVERABLE:
            raise
        except Exception as error:
            self._tag_failed(message, error)
            raise

    def expire_workflows(self) -> None:
        now = datetime.now(UTC)
        for status in sorted(self.active):
            records = self.records.list(EXPIRY_BATCH, status, oldest_first=True)
            for record in records:
                updated_at = datetime.fromisoformat(record["updated_at"])
                expired = self.timed_out(record["status"], updated_at, now, self.workflow_timeout)
                if expired:
                    self.messages.fail(record["id"], record["workflow_id"], "AgentTimedOut")

    def _tag_failed(self, message: KafkaMessage, error: Exception) -> None:
        if message.topic not in RECORD_TOPICS:
            return
        error_type = type(error).__name__
        try:
            envelope = RecordMessage.model_validate(message.payload)
            if envelope.record_id is not None:
                self.messages.fail(envelope.record_id, envelope.workflow_id, error_type)
        except Exception:
            logger.exception("Could not mark the %s record of a failed %s message", self.domain, message.topic)

    def _on_request(self, payload: dict[str, Any]) -> None:
        request = WorkflowRequest.model_validate(payload)
        route = self.requests.get(request.kind)
        if route is None:
            raise InvalidMessageError(f"unsupported {self.domain} request: {request.kind}")
        route(request)

    def _on_executor_return(self, payload: dict[str, Any]) -> None:
        executor_return = ExecutorReturn.model_validate(payload)
        route = self.executor_returns.get(executor_return.action)
        if route is None:
            raise InvalidMessageError(f"unexpected {self.domain} executor return: {executor_return.action}")
        route(executor_return)

    def _on_delete(self, request: WorkflowRequest) -> None:
        record_id = required_record(request)
        self.records.delete(record_id)


def required_record(request: WorkflowRequest) -> str:
    if request.record_id is None:
        raise InvalidMessageError(f"{request.kind} request names no record")
    return request.record_id


class DomainRouter:
    def __init__(self, handlers: Mapping[AgentDomain, Handler]):
        self.handlers = handlers

    def route_message(self, message: KafkaMessage) -> None:
        try:
            domain = AgentDomain(message.payload["domain"])
            handler = self.handlers[domain]
        except (KeyError, ValueError) as exc:
            raise InvalidMessageError(f"no enabled workflow for {message.topic} message") from exc
        handler(message)
