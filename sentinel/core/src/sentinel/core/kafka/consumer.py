import json
import logging
import signal
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from confluent_kafka import TIMESTAMP_NOT_AVAILABLE, Consumer
from sentinel.core.config.settings import KafkaClientSettings
from sentinel.core.kafka.config import client_config, topic_name
from sentinel.core.kafka.contracts import UNDELIVERABLE, InvalidMessageError, KafkaMessage, KafkaTopic

logger = logging.getLogger(__name__)


def _published_at(timestamp: tuple[int, int]) -> datetime:
    kind, milliseconds = timestamp
    if kind == TIMESTAMP_NOT_AVAILABLE:
        return datetime.now(UTC)
    return datetime.fromtimestamp(milliseconds / 1000, UTC)


def _payload(value: bytes | None) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise InvalidMessageError("Kafka event is not UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidMessageError("Kafka event must be a JSON object")
    return payload


class KafkaConsumer:
    def __init__(self, settings: KafkaClientSettings, topic: KafkaTopic, group: str, heartbeat: Path):
        kafka = settings.kafka
        client = client_config(settings)
        consumer_config = {
            **client,
            "group.id": f"{kafka.consumer_group}-{group}",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "max.poll.interval.ms": kafka.max_poll_interval_seconds * 1000,
        }
        self._consumer = Consumer(consumer_config)
        name = topic_name(settings, topic)
        self._consumer.subscribe([name])
        self._topic = topic
        self._heartbeat = heartbeat
        self._stopped = threading.Event()

    def run(self, handler: Callable[[KafkaMessage], None]) -> None:
        while not self._stopped.is_set():
            self._heartbeat.touch()
            message = self._consumer.poll(1.0)
            if message is None:
                continue
            error = message.error()
            if error:
                raise RuntimeError(f"Kafka consumer failed: {error}")
            position = (message.topic(), message.partition(), message.offset())

            def commit_now() -> None:
                self._consumer.commit(message=message, asynchronous=False)

            try:
                value = message.value()
                payload = _payload(value)
                timestamp = message.timestamp()
                published_at = _published_at(timestamp)
                parsed = KafkaMessage(self._topic, payload, published_at, commit_now)
                handler(parsed)
            except UNDELIVERABLE as exc:
                logger.warning(
                    "Discarding undeliverable Kafka message topic=%s partition=%s offset=%s error=%s",
                    *position,
                    exc,
                )
            except Exception:
                logger.exception("Discarding Kafka message that failed topic=%s partition=%s offset=%s", *position)
            self._consumer.commit(message=message, asynchronous=False)

    def stop(self) -> None:
        self._stopped.set()

    def close(self) -> None:
        self._consumer.close()


def _exit_now(signum: int, _frame: Any) -> None:
    raise SystemExit(128 + signum)


def exit_on_signals() -> None:
    """Exit at once when asked to terminate during startup, before ``stop_on_signals`` takes over.

    The worker runs as PID 1, which silently ignores a termination signal it has no handler for.
    """
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(stop_signal, _exit_now)


def stop_on_signals(stop: Callable[[], None]) -> None:
    for stop_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(stop_signal, lambda _signum, _frame: stop())
