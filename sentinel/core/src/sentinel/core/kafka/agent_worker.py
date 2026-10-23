import logging
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel
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
    RunFailure,
)
from sentinel.core.kafka.producer import publish_return

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/sentinel-worker-heartbeat")


def return_request(kind: RequestKind, payload: dict[str, Any]) -> dict[str, Any]:
    contract = IncidentRequest if kind is RequestKind.INCIDENT else PrReviewRequest
    request = contract.model_validate(payload)
    return request.model_dump(mode="json")


@dataclass(frozen=True)
class Agent:
    settings: KafkaClientSettings
    topic: KafkaTopic
    return_topic: KafkaTopic
    kind: RequestKind
    execute: Callable[[dict[str, Any], datetime], BaseModel]
    run_timeout_seconds: int


def command_handler(agent: Agent) -> Callable[[KafkaMessage], None]:
    """Run each command against a deadline counted from when the workflow published it.

    ``execute`` returns the run's result, or a ``RunFailure`` with the run's audit trail when the run failed;
    an exception it raises becomes a ``RunFailure`` without one. A command that waited in the queue past its
    deadline fails at once instead of starting work the workflow has already given up on.
    """

    def handle(message: KafkaMessage) -> None:
        command = AgentCommand.model_validate(message.payload)
        deadline = deadline_after(message.published_at, agent.run_timeout_seconds)
        try:
            value = agent.execute(command.payload, deadline)
        except Exception as exc:
            logger.exception("Agent failed workflow_id=%s", command.workflow_id)
            value = RunFailure(error=type(exc).__name__)
        failure = value if isinstance(value, RunFailure) else None
        result = None if failure else value.model_dump(mode="json")
        request = return_request(agent.kind, command.payload)
        event = AgentReturn(
            kind=agent.kind,
            record_id=command.record_id,
            workflow_id=command.workflow_id,
            request=request,
            result=result,
            failure=failure,
        )
        publish_return(agent.settings, agent.return_topic, event)

    return handle


def run_agents(agents: Sequence[Agent]) -> None:
    """Consume every agent's commands in one process, one thread per agent, until a signal or an agent stops.

    When one agent ends, for a signal or a consumer failure, every agent stops and the process exits.
    """
    consumers = [KafkaConsumer(agent.settings, agent.topic, agent.kind.value, HEARTBEAT) for agent in agents]

    def stop() -> None:
        for consumer in consumers:
            consumer.stop()

    stop_on_signals(stop)
    try:
        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            futures = []
            for consumer, agent in zip(consumers, agents, strict=True):
                handler = command_handler(agent)
                future = pool.submit(consumer.run, handler)
                futures.append(future)
            wait(futures, return_when=FIRST_COMPLETED)
            stop()
            for future in futures:
                future.result()
    finally:
        stop()
        for consumer in consumers:
            consumer.close()
