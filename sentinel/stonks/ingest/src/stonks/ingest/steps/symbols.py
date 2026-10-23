import logging
from datetime import UTC, date, datetime

from stonks.ingest.domain.listings import choose_symbol, needs_lookup, preferred_suffixes, tradable_listings
from stonks.ingest.domain.models import Constituent, Listings, Selection, Universe
from stonks.ingest.domain.universe import build_universe, require_size
from stonks.ingest.runtime import IngestRuntime
from stonks.ingest.sources.yahoo import SEARCH_SOURCE, equity_symbols
from stonks.ingest.storage.store import SymbolLookup

logger = logging.getLogger(__name__)


class SymbolsStep:
    def __init__(self, runtime: IngestRuntime):
        self.runtime = runtime
        self.universe = runtime.settings.universe

    def execute(self, trade_date: date) -> Universe:
        candidates = self.runtime.store.read_candidates(trade_date)
        countries = self.runtime.store.read_countries()
        listings = tradable_listings(countries)
        symbols = self.resolve_symbols(trade_date, candidates.selection, listings)
        universe = build_universe(candidates, symbols, self.universe.symbol_overrides)
        selected = len(universe.instruments)
        require_size(selected, self.universe.min_instruments)
        universe_key = self.runtime.store.write_universe(trade_date, universe)
        logger.info(
            "universe_selected eligible=%d selected=%d rejected=%d universe=%s",
            len(candidates.selection.eligible),
            selected,
            len(universe.rejections),
            universe_key,
        )
        return universe

    def resolve_symbols(self, trade_date: date, selection: Selection, listings: Listings) -> dict[str, str]:
        known = self.runtime.store.read_symbols()
        overrides = self.universe.symbol_overrides
        missing = [constituent for constituent in selection.eligible if needs_lookup(constituent, known, overrides)]
        if not missing:
            return known
        symbols = dict(known)
        lookups = []
        started_at = datetime.now(UTC)
        try:
            for constituent in missing:
                lookup = self.lookup_symbol(constituent, listings)
                lookups.append(lookup)
                if lookup.symbol:
                    symbols[constituent.isin] = lookup.symbol
        finally:
            self.record_lookups(trade_date, started_at, lookups, symbols)
        return symbols

    def lookup_symbol(self, constituent: Constituent, listings: Listings) -> SymbolLookup:
        response = self.runtime.search.search(constituent.isin)
        candidates = equity_symbols(response)
        preferred = preferred_suffixes(constituent, listings)
        symbol = choose_symbol(candidates, preferred, listings.suffixes)
        if symbol is None:
            logger.warning("symbol_unresolved isin=%s name=%s", constituent.isin, constituent.name)
        return SymbolLookup(isin=constituent.isin, symbol=symbol, response=response)

    def record_lookups(
        self, trade_date: date, started_at: datetime, lookups: list[SymbolLookup], symbols: dict[str, str]
    ) -> None:
        if not lookups:
            return
        self.runtime.store.write_symbol_lookups(SEARCH_SOURCE, trade_date, started_at, lookups)
        key = self.runtime.store.write_symbols(symbols)
        logger.info("symbols_recorded looked_up=%d known=%d reference=%s", len(lookups), len(symbols), key)
