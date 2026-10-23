from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from stonks.core.http import HttpSource, Throttle, http_client
from stonks.core.objects import ObjectStore, s3_client
from stonks.ingest.config.settings import Settings
from stonks.ingest.sources.xtrackers import XtrackersConstituents
from stonks.ingest.sources.yahoo import YahooChart, YahooSearch
from stonks.ingest.storage.store import IngestStore


@dataclass(frozen=True)
class IngestRuntime:
    settings: Settings
    constituents: XtrackersConstituents
    search: YahooSearch
    chart: YahooChart
    store: IngestStore


@contextmanager
def ingest_runtime(settings: Settings) -> Iterator[IngestRuntime]:
    with ExitStack() as resources:
        s3 = s3_client(settings)
        resources.callback(s3.close)
        client = http_client(settings.http)
        resources.callback(client.close)
        http = HttpSource(client, settings.http)
        throttle = Throttle(settings.yahoo.min_interval_seconds)
        constituents = XtrackersConstituents(http, settings.universe.constituents_url)
        search = YahooSearch(http, settings.yahoo, throttle)
        chart = YahooChart(http, settings.yahoo, throttle)
        objects = ObjectStore(s3, settings.s3)
        store = IngestStore(objects, settings.storage)
        yield IngestRuntime(settings=settings, constituents=constituents, search=search, chart=chart, store=store)
