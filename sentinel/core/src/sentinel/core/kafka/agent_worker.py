import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from sentinel.core.config.settings import KafkaClientSettings
from sentinel.core.contracts.incidents import IncidentRequest
from sentinel.core.contracts.reviews import PrReviewRequest
from sentinel.core.deadline import deadline_after
from sentinel.core.kafka.consumer import KafkaConsumer, stop_on_signals
from sentinel.core.kafka.contracts import (
    AgentCommand,
    AgentReturn,
    KafkaMessage,
    KafkaTopic,
    RequestKind,
)
from sentinel.core.kafka.producer import publish_return

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/sentinel-worker-heartbeat")


def return_request(kind: RequestKind, payload: dict[str, Any]) -> dict[str, Any]:
    contract = IncidentRequest if kind is RequestKind.INCIDENT else PrReviewRequest
    request = contract.model_validate(payload)
    return request.model_dump(mode="json")


def run_agent(
    settings: KafkaClientSettings,
    topic: KafkaTopic,
    return_topic: KafkaTopic,
    kind: RequestKind,
    execute: Callable[[dict[str, Any], datetime], Any],
    *,
    run_timeout_seconds: int,
) -> None:
    """Run each command against a deadline counted from when the workflow published it.

    A command that waited in the queue past its deadline fails at once instead of starting work the
    workflow has already given up on.
    """
    consumer = KafkaConsumer(settings, topic, kind.value, HEARTBEAT)
    stop_on_signals(consumer.stop)

    def handle(message: KafkaMessage) -> None:
        command = AgentCommand.model_validate(message.payload)
        deadline = deadline_after(message.published_at, run_timeout_seconds)
        try:
            value = execute(command.payload, deadline)
            result = value.model_dump(mode="json")
            error = None
        except Exception as exc:
            logger.exception("Agent failed workflow_id=%s", command.workflow_id)
            result = None
            error = type(exc).__name__
        request = return_request(kind, command.payload)
        event = AgentReturn(kind=kind, workflow_id=command.workflow_id, request=request, result=result, error=error)
        publish_return(settings, return_topic, event)

    try:
        consumer.run(handle)
    finally:
        consumer.close()
