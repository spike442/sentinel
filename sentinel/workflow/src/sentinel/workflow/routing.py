import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any

from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import (
    UNDELIVERABLE,
    ExecutorAction,
    ExecutorReturn,
    InvalidMessageError,
    KafkaMessage,
    KafkaTopic,
    RequestKind,
    WorkflowRequest,
)

logger = logging.getLogger(__name__)

Handler = Callable[[KafkaMessage], None]
PayloadHandler = Callable[[dict[str, Any]], None]
SHARED_TOPICS = (KafkaTopic.WORKFLOW_REQUESTS, KafkaTopic.EXECUTOR_RETURNS)


class DomainWorkflow(ABC):
    """Dispatch one domain's messages by topic; shared topics then dispatch by request kind or executor action.

    A message whose handling fails marks its record failed through ``fail_record``; nothing retries it, and an
    operator replays the record from the UI.
    """

    def __init__(
        self,
        domain: AgentDomain,
        topics: Mapping[KafkaTopic, PayloadHandler],
        requests: Mapping[RequestKind, Callable[[WorkflowRequest], None]],
        executor_returns: Mapping[ExecutorAction, Callable[[ExecutorReturn], None]],
    ):
        self.domain = domain
        self.topics: dict[KafkaTopic, PayloadHandler] = {
            **topics,
            KafkaTopic.WORKFLOW_REQUESTS: self._on_request,
            KafkaTopic.EXECUTOR_RETURNS: self._on_executor_return,
        }
        self.requests = requests
        self.executor_returns = executor_returns

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

    @abstractmethod
    def fail_record(self, topic: KafkaTopic, payload: dict[str, Any], error: str) -> None:
        pass

    def _tag_failed(self, message: KafkaMessage, error: Exception) -> None:
        error_type = type(error).__name__
        try:
            self.fail_record(message.topic, message.payload, error_type)
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
