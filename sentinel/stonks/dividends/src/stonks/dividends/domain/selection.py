from collections.abc import Mapping, Sequence
from datetime import date

from stonks.dividends.domain.models import DividendDates, DividendStatus, Instrument


def needs_research(entry: DividendDates | None, trade_date: date, recheck_days: int) -> bool:
    if entry is None:
        return True
    upcoming = entry.ex_date is not None and entry.ex_date >= trade_date
    if entry.status is DividendStatus.CONFIRMED and upcoming:
        return False
    age = (trade_date - entry.checked_on).days
    return age >= recheck_days


def research_order(instrument: Instrument, entries: Mapping[str, DividendDates]) -> tuple[bool, date, str]:
    entry = entries.get(instrument.isin)
    if entry is None:
        return (False, date.min, instrument.isin)
    return (True, entry.checked_on, instrument.isin)


def research_queue(
    instruments: Sequence[Instrument],
    entries: Mapping[str, DividendDates],
    trade_date: date,
    *,
    recheck_days: int,
    limit: int,
) -> list[Instrument]:
    due = [item for item in instruments if needs_research(entries.get(item.isin), trade_date, recheck_days)]
    ordered = sorted(due, key=lambda item: research_order(item, entries))
    return ordered[:limit]


def failure_ratio(failed: int, total: int) -> float:
    return failed / total if total else 0.0
