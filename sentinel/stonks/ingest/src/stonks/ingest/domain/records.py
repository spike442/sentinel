from collections.abc import Mapping
from dataclasses import asdict
from datetime import date

from stonks.ingest.domain.bars import BarWatermark
from stonks.ingest.domain.models import Candidates, Constituent, Country, Instrument, Rejection, Selection, Universe


def country_from_record(code: str, record: Mapping) -> Country:
    return Country(
        code=code,
        name=record["name"],
        pea=record["pea"],
        exchange=record["exchange"],
        suffix=record["suffix"],
    )


def countries_from_document(document: Mapping) -> dict[str, Country]:
    return {code: country_from_record(code, record) for code, record in document.items()}


def instrument_from_record(record: Mapping) -> Instrument:
    return Instrument(
        isin=record["isin"],
        symbol=record["symbol"],
        name=record["name"],
        country=record["country"],
        currency=record["currency"],
        main_exchange=record["main_exchange"],
        sector=record["sector"],
        weight=record["weight"],
    )


def rejection_from_record(record: Mapping) -> Rejection:
    return Rejection(isin=record["isin"], name=record["name"], reason=record["reason"])


def universe_from_snapshot(snapshot: Mapping) -> Universe:
    universe = snapshot["universe"]
    instruments = [instrument_from_record(record) for record in universe["instruments"]]
    rejections = [rejection_from_record(record) for record in universe["rejections"]]
    return Universe(
        source=universe["source"],
        downloaded_at=universe["downloaded_at"],
        instruments=instruments,
        rejections=rejections,
    )


def universe_snapshot(trade_date: date, universe: Universe) -> dict:
    instruments = [asdict(item) for item in universe.instruments]
    rejections = [asdict(item) for item in universe.rejections]
    return {
        "trade_date": trade_date.isoformat(),
        "universe": {
            "source": universe.source,
            "downloaded_at": universe.downloaded_at,
            "selected": len(instruments),
            "rejected": len(rejections),
            "instruments": instruments,
            "rejections": rejections,
        },
    }


def constituent_from_record(record: Mapping) -> Constituent:
    return Constituent(
        isin=record["isin"],
        name=record["name"],
        currency=record["currency"],
        weight=record["weight"],
        main_exchange=record["main_exchange"],
        sector=record["sector"],
    )


def candidates_snapshot(trade_date: date, candidates: Candidates) -> dict:
    eligible = [asdict(item) for item in candidates.selection.eligible]
    rejections = [asdict(item) for item in candidates.selection.rejections]
    return {
        "trade_date": trade_date.isoformat(),
        "candidates": {
            "source": candidates.source,
            "downloaded_at": candidates.downloaded_at,
            "eligible": eligible,
            "rejections": rejections,
        },
    }


def candidates_from_snapshot(snapshot: Mapping) -> Candidates:
    record = snapshot["candidates"]
    eligible = [constituent_from_record(item) for item in record["eligible"]]
    rejections = [rejection_from_record(item) for item in record["rejections"]]
    selection = Selection(eligible=eligible, rejections=rejections)
    return Candidates(source=record["source"], downloaded_at=record["downloaded_at"], selection=selection)


def watermark_from_record(record: Mapping) -> BarWatermark:
    first_date = date.fromisoformat(record["first_date"])
    last_date = date.fromisoformat(record["last_date"])
    splits = frozenset(date.fromisoformat(day) for day in record["splits"])
    return BarWatermark(symbol=record["symbol"], first_date=first_date, last_date=last_date, splits=splits)


def watermark_record(watermark: BarWatermark) -> dict:
    splits = sorted(day.isoformat() for day in watermark.splits)
    return {
        "symbol": watermark.symbol,
        "first_date": watermark.first_date.isoformat(),
        "last_date": watermark.last_date.isoformat(),
        "splits": splits,
    }
