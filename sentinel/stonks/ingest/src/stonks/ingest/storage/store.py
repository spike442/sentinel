from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from stonks.core.objects import ObjectStore, stamped
from stonks.core.settings import StorageConfig
from stonks.ingest.domain.bars import BarWatermark
from stonks.ingest.domain.models import Candidates, Country, Universe
from stonks.ingest.domain.records import (
    candidates_from_snapshot,
    candidates_snapshot,
    countries_from_document,
    universe_from_snapshot,
    universe_snapshot,
    watermark_from_record,
    watermark_record,
)

SYMBOLS = "yahoo-symbols.json"
BAR_WATERMARKS = "yahoo-bar-watermarks.json"
COUNTRIES = "countries.json"
CANDIDATES = "candidates.json"
UNIVERSE = "universe.json"


class MissingCandidates(LookupError):
    pass


class MissingUniverse(LookupError):
    pass


class MissingCountries(LookupError):
    pass


@dataclass(frozen=True)
class SymbolLookup:
    isin: str
    symbol: str | None
    response: dict


@dataclass(frozen=True)
class ChartFetch:
    isin: str
    symbol: str
    start: date
    end: date
    full: bool
    fetched_at: datetime
    error: str | None
    response: dict | None


def symbol_lookup_record(lookup: SymbolLookup) -> dict:
    return {"isin": lookup.isin, "symbol": lookup.symbol, "response": lookup.response}


def chart_fetch_record(fetch: ChartFetch) -> dict:
    return {
        "isin": fetch.isin,
        "symbol": fetch.symbol,
        "start": fetch.start.isoformat(),
        "end": fetch.end.isoformat(),
        "full": fetch.full,
        "fetched_at": fetch.fetched_at.isoformat(),
        "error": fetch.error,
        "response": fetch.response,
    }


class IngestStore:
    def __init__(self, objects: ObjectStore, storage: StorageConfig):
        self.objects = objects
        self.raw_prefix = storage.raw_prefix.rstrip("/")
        self.universe_prefix = storage.universe_prefix.rstrip("/")
        self.reference_prefix = storage.reference_prefix.rstrip("/")

    def raw_key(self, source: str, trade_date: date, filename: str) -> str:
        return f"{self.raw_prefix}/source={source}/trade_date={trade_date.isoformat()}/{filename}"

    def universe_key(self, trade_date: date, name: str) -> str:
        return f"{self.universe_prefix}/trade_date={trade_date.isoformat()}/{name}"

    def reference_key(self, name: str) -> str:
        return f"{self.reference_prefix}/{name}"

    def write_constituents(self, source: str, trade_date: date, downloaded_at: datetime, body: str) -> str:
        filename = stamped("constituents", downloaded_at, "csv")
        key = self.raw_key(source, trade_date, filename)
        return self.objects.put_text(key, body, "text/csv")

    def write_symbol_lookups(
        self, source: str, trade_date: date, started_at: datetime, lookups: list[SymbolLookup]
    ) -> str:
        filename = stamped("lookups", started_at, "jsonl")
        key = self.raw_key(source, trade_date, filename)
        records = [symbol_lookup_record(lookup) for lookup in lookups]
        return self.objects.put_json_lines(key, records)

    def write_chart_fetches(
        self, source: str, trade_date: date, started_at: datetime, fetches: list[ChartFetch]
    ) -> str:
        filename = stamped("chart", started_at, "jsonl")
        key = self.raw_key(source, trade_date, filename)
        records = [chart_fetch_record(fetch) for fetch in fetches]
        return self.objects.put_json_lines(key, records)

    def write_candidates(self, trade_date: date, candidates: Candidates) -> str:
        key = self.universe_key(trade_date, CANDIDATES)
        snapshot = candidates_snapshot(trade_date, candidates)
        return self.objects.put_json(key, snapshot)

    def read_candidates(self, trade_date: date) -> Candidates:
        key = self.universe_key(trade_date, CANDIDATES)
        snapshot = self.objects.require_json(key, MissingCandidates, f"run the universe step for {trade_date} first")
        return candidates_from_snapshot(snapshot)

    def write_universe(self, trade_date: date, universe: Universe) -> str:
        key = self.universe_key(trade_date, UNIVERSE)
        snapshot = universe_snapshot(trade_date, universe)
        return self.objects.put_json(key, snapshot)

    def read_universe(self, trade_date: date) -> Universe:
        key = self.universe_key(trade_date, UNIVERSE)
        snapshot = self.objects.require_json(key, MissingUniverse, f"run the symbols step for {trade_date} first")
        return universe_from_snapshot(snapshot)

    def read_countries(self) -> dict[str, Country]:
        key = self.reference_key(COUNTRIES)
        document = self.objects.require_json(key, MissingCountries, "upload it with task s3")
        return countries_from_document(document)

    def read_symbols(self) -> dict[str, str]:
        key = self.reference_key(SYMBOLS)
        return self.objects.find_json(key) or {}

    def write_symbols(self, symbols: Mapping[str, str]) -> str:
        key = self.reference_key(SYMBOLS)
        document = dict(symbols)
        return self.objects.put_json(key, document)

    def read_watermarks(self) -> dict[str, BarWatermark]:
        key = self.reference_key(BAR_WATERMARKS)
        records = self.objects.find_json(key) or {}
        return {isin: watermark_from_record(record) for isin, record in records.items()}

    def write_watermarks(self, watermarks: Mapping[str, BarWatermark]) -> str:
        key = self.reference_key(BAR_WATERMARKS)
        records = {isin: watermark_record(watermark) for isin, watermark in watermarks.items()}
        return self.objects.put_json(key, records)
