from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

from prometheus_client import Counter, start_http_server
from prometheus_client.core import REGISTRY, GaugeMetricFamily
from prometheus_client.registry import Collector

if TYPE_CHECKING:
    from sentinel.core.persistence.queries import IncidentReader, PrReviewReader

logger = logging.getLogger(__name__)

METRICS_PORT = 9100

cluster_alerts_processed = Counter(
    "sentinel_cluster_alert_events_total",
    "Alertmanager cluster alert events handled by the incident workflow",
    ["result"],
)


class StateCollector(Collector):
    def __init__(self, incidents: IncidentReader | None, reviews: PrReviewReader | None):
        self.incidents = incidents
        self.reviews = reviews

    def collect(self) -> Iterator[GaugeMetricFamily]:
        up = GaugeMetricFamily("sentinel_state_up", "Whether Sentinel could read its PostgreSQL state")
        try:
            state = self._state()
            families = list(state)
        except Exception:
            logger.exception("Could not collect Sentinel state metrics")
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up
        yield from families

    def _state(self) -> Iterator[GaugeMetricFamily]:
        if self.incidents is not None:
            by_status = GaugeMetricFamily("sentinel_incidents", "Incidents by status", labels=["status"])
            counts = self.incidents.status_counts()
            for status, count in counts.items():
                by_status.add_metric([status], count)
            yield by_status
        if self.reviews is not None:
            by_status = GaugeMetricFamily("sentinel_pr_reviews", "Pull-request reviews by status", labels=["status"])
            counts = self.reviews.status_counts()
            for status, count in counts.items():
                by_status.add_metric([status], count)
            yield by_status


def serve(collector: Collector | None = None) -> None:
    if collector is not None:
        REGISTRY.register(collector)
    start_http_server(METRICS_PORT)
