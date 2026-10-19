import logging
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from importlib.metadata import version
from pathlib import Path

from sentinel.core.config.common import CommonSettings
from sentinel.core.kafka.consumer import KafkaConsumer, stop_on_signals
from sentinel.core.kafka.contracts import KafkaMessage, KafkaTopic
from sentinel.core.observability.metrics import serve

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/sentinel-workflow-heartbeat")
Route = tuple[KafkaTopic, Callable[[KafkaMessage], None]]


def run(
    settings: CommonSettings,
    routes: Sequence[Route],
    jobs: Sequence[Callable[[threading.Event], None]],
) -> None:
    consumers = []
    for topic, _ in routes:
        group = topic.value.replace("_", "-")
        consumer = KafkaConsumer(settings, topic, group, HEARTBEAT)
        consumers.append(consumer)
    stopped = threading.Event()

    def stop() -> None:
        stopped.set()
        for consumer in consumers:
            consumer.stop()

    stop_on_signals(stop)

    try:
        serve()
        release = version("sentinel-core")
        logger.info("Sentinel workflow ready version=%s", release)
        workers = len(routes) + len(jobs)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            for consumer, (_, handler) in zip(consumers, routes, strict=True):
                future = pool.submit(consumer.run, handler)
                futures.append(future)
            for job in jobs:
                future = pool.submit(job, stopped)
                futures.append(future)
            wait(futures, return_when=FIRST_COMPLETED)
            stop()
            for future in futures:
                future.result()
    finally:
        stop()
        for consumer in consumers:
            consumer.close()
