from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from stonks.ingest.domain.models import Instrument


@dataclass(frozen=True)
class BarWatermark:
    symbol: str
    first_date: date
    last_date: date
    splits: frozenset[date]


@dataclass(frozen=True)
class FetchWindow:
    isin: str
    symbol: str
    start: date
    end: date
    full: bool


def years_before(day: date, years: int) -> date:
    target_year = day.year - years
    if day.month == 2 and day.day == 29:
        return date(target_year, 2, 28)
    return day.replace(year=target_year)


def tracks(watermark: BarWatermark | None, symbol: str) -> bool:
    return watermark is not None and watermark.symbol == symbol


def plan_fetch(
    instrument: Instrument,
    watermark: BarWatermark | None,
    trade_date: date,
    *,
    history_years: int,
    overlap_days: int,
) -> FetchWindow | None:
    isin = instrument.isin
    symbol = instrument.symbol
    if not tracks(watermark, symbol):
        start = years_before(trade_date, history_years)
        return FetchWindow(isin=isin, symbol=symbol, start=start, end=trade_date, full=True)
    start = watermark.last_date - timedelta(days=overlap_days)
    if start > trade_date:
        return None
    return FetchWindow(isin=isin, symbol=symbol, start=start, end=trade_date, full=False)


def full_window(window: FetchWindow, watermark: BarWatermark | None, history_years: int) -> FetchWindow:
    start = years_before(window.end, history_years)
    if tracks(watermark, window.symbol):
        start = min(start, watermark.first_date)
    return FetchWindow(isin=window.isin, symbol=window.symbol, start=start, end=window.end, full=True)


def needs_full_refresh(window: FetchWindow, watermark: BarWatermark | None, split_dates: Collection[date]) -> bool:
    if window.full:
        return False
    seen = watermark.splits if tracks(watermark, window.symbol) else frozenset()
    unseen = frozenset(split_dates) - seen
    return bool(unseen)


def advance_watermark(
    watermark: BarWatermark | None,
    window: FetchWindow,
    bar_dates: Iterable[date],
    split_dates: Iterable[date],
    trade_date: date,
) -> BarWatermark | None:
    stored = [day for day in bar_dates if day <= trade_date]
    if not stored:
        return None
    first_date = min(stored)
    last_date = max(stored)
    splits = frozenset(split_dates)
    if tracks(watermark, window.symbol):
        first_date = min(first_date, watermark.first_date)
        last_date = max(last_date, watermark.last_date)
        splits = splits | watermark.splits
    return BarWatermark(symbol=window.symbol, first_date=first_date, last_date=last_date, splits=splits)


def failure_ratio(failed: int, total: int) -> float:
    return failed / total if total else 0.0
