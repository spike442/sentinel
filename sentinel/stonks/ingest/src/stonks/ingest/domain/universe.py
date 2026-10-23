from collections.abc import Collection, Mapping

from stonks.ingest.domain.listings import resolved_symbol
from stonks.ingest.domain.models import Candidates, Constituent, Instrument, Rejection, Universe


class UniverseTooSmall(RuntimeError):
    pass


def require_size(selected: int, minimum: int) -> None:
    if selected < minimum:
        raise UniverseTooSmall(f"{selected} instruments selected, expected at least {minimum}")


def without_ignored(constituents: list[Constituent], ignored: Collection[str]) -> list[Constituent]:
    return [constituent for constituent in constituents if constituent.isin not in ignored]


def rejection_reason(symbol: str | None, taken: set[str]) -> str | None:
    if symbol is None:
        return "unresolved_symbol"
    if symbol in taken:
        return "duplicate_symbol"
    return None


def build_universe(candidates: Candidates, symbols: Mapping[str, str], overrides: Mapping[str, str]) -> Universe:
    instruments = []
    rejections = list(candidates.selection.rejections)
    taken = set()
    for constituent in candidates.selection.eligible:
        symbol = resolved_symbol(constituent, symbols, overrides)
        reason = rejection_reason(symbol, taken)
        if reason is not None:
            rejected = Rejection(constituent.isin, constituent.name, reason)
            rejections.append(rejected)
            continue
        taken.add(symbol)
        selected = Instrument(
            isin=constituent.isin,
            symbol=symbol,
            name=constituent.name,
            country=constituent.country,
            currency=constituent.currency,
            main_exchange=constituent.main_exchange,
            sector=constituent.sector,
            weight=constituent.weight,
        )
        instruments.append(selected)
    return Universe(
        source=candidates.source,
        downloaded_at=candidates.downloaded_at,
        instruments=instruments,
        rejections=rejections,
    )
