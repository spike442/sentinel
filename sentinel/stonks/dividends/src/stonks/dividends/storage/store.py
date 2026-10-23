from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from stonks.core.objects import ObjectStore, parse_json_lines, stamped
from stonks.core.settings import StorageConfig
from stonks.dividends.domain.models import DividendDates, Instrument, Venue
from stonks.dividends.domain.records import (
    dividend_dates_from_record,
    dividend_dates_record,
    instruments_from_snapshot,
    venues_from_document,
)

RESEARCH_SOURCE = "dividend_agent"
DIVIDEND_DATES = "dividend-dates.json"
COUNTRIES = "countries.json"
UNIVERSE = "universe.json"


class MissingUniverse(LookupError):
    pass


class MissingCountries(LookupError):
    pass


@dataclass(frozen=True)
class ResearchRecord:
    isin: str
    symbol: str
    researched_at: datetime
    error: str | None
    answer: dict | None
    audit: list[dict]
    tool_budget: dict


def research_record(record: ResearchRecord) -> dict:
    return {
        "isin": record.isin,
        "symbol": record.symbol,
        "researched_at": record.researched_at.isoformat(),
        "error": record.error,
        "answer": record.answer,
        "audit": record.audit,
        "tool_budget": record.tool_budget,
    }


def research_from_record(record: dict) -> ResearchRecord:
    researched_at = datetime.fromisoformat(record["researched_at"])
    return ResearchRecord(
        isin=record["isin"],
        symbol=record["symbol"],
        researched_at=researched_at,
        error=record["error"],
        answer=record["answer"],
        audit=record["audit"],
        tool_budget=record["tool_budget"],
    )


class DividendStore:
    def __init__(self, objects: ObjectStore, storage: StorageConfig):
        self.objects = objects
        self.raw_prefix = storage.raw_prefix.rstrip("/")
        self.universe_prefix = storage.universe_prefix.rstrip("/")
        self.reference_prefix = storage.reference_prefix.rstrip("/")

    def research_prefix(self, trade_date: date) -> str:
        return f"{self.raw_prefix}/source={RESEARCH_SOURCE}/trade_date={trade_date.isoformat()}/"

    def reference_key(self, name: str) -> str:
        return f"{self.reference_prefix}/{name}"

    def write_research(self, trade_date: date, started_at: datetime, records: list[ResearchRecord]) -> str:
        prefix = self.research_prefix(trade_date)
        filename = stamped("research", started_at, "jsonl")
        lines = [research_record(record) for record in records]
        return self.objects.put_json_lines(f"{prefix}{filename}", lines)

    def read_research(self, trade_date: date) -> list[ResearchRecord]:
        prefix = self.research_prefix(trade_date)
        keys = self.objects.keys(prefix)
        records = []
        for key in keys:
            text = self.objects.get_text(key)
            lines = parse_json_lines(text)
            records.extend(research_from_record(line) for line in lines)
        return records

    def read_instruments(self, trade_date: date) -> list[Instrument]:
        key = f"{self.universe_prefix}/trade_date={trade_date.isoformat()}/{UNIVERSE}"
        snapshot = self.objects.require_json(key, MissingUniverse, f"run the symbols step for {trade_date} first")
        return instruments_from_snapshot(snapshot)

    def read_venues(self) -> dict[str, Venue]:
        key = self.reference_key(COUNTRIES)
        document = self.objects.require_json(key, MissingCountries, "upload it with task s3")
        return venues_from_document(document)

    def read_dividend_dates(self) -> dict[str, DividendDates]:
        key = self.reference_key(DIVIDEND_DATES)
        records = self.objects.find_json(key) or {}
        return {isin: dividend_dates_from_record(isin, record) for isin, record in records.items()}

    def write_dividend_dates(self, entries: Mapping[str, DividendDates]) -> str:
        key = self.reference_key(DIVIDEND_DATES)
        records = {isin: dividend_dates_record(entry) for isin, entry in entries.items()}
        return self.objects.put_json(key, records)
