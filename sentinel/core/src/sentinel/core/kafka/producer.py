import logging
import threading

from confluent_kafka import Producer
from pydantic import BaseModel
from sentinel.core.config.settings import KafkaClientSettings
from sentinel.core.kafka.config import client_config, topic_name
from sentinel.core.kafka.contracts import AgentReturn, ExecutorReturn, KafkaTopic, RunFailure

logger = logging.getLogger(__name__)

MAX_RETURN_BYTES = 800_000

_producer: Producer | None = None
_producer_lock = threading.Lock()


def _shared_producer(settings: KafkaClientSettings) -> Producer:
    global _producer
    with _producer_lock:
        if _producer is None:
            config = client_config(settings)
            _producer = Producer(config)
    return _producer


def publish(settings: KafkaClientSettings, topic: KafkaTopic, key: str, message: BaseModel) -> None:
    producer = _shared_producer(settings)
    failures = []

    def delivered(error, _message) -> None:
        if error:
            failures.append(error)

    value = message.model_dump_json()
    name = topic_name(settings, topic)
    producer.produce(name, key=key, value=value, on_delivery=delivered)
    pending = producer.flush(30)
    if pending or failures:
        raise RuntimeError(f"failed to publish {name}: {failures}")


def publish_return(settings: KafkaClientSettings, topic: KafkaTopic, event: AgentReturn | ExecutorReturn) -> None:
    serialized = event.model_dump_json()
    size = len(serialized.encode())
    if size > MAX_RETURN_BYTES:
        logger.error("Return exceeds the Kafka limit topic=%s workflow_id=%s bytes=%s", topic, event.workflow_id, size)
        too_large = "ResultTooLarge"
        if isinstance(event, AgentReturn):
            failure = RunFailure(error=too_large)
            event = event.model_copy(update={"result": None, "failure": failure})
        else:
            event = event.model_copy(update={"result": None, "error": too_large})
    publish(settings, topic, event.workflow_id, event)
