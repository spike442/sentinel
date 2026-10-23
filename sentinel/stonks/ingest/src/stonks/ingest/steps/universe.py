import logging
from datetime import UTC, date, datetime

from stonks.ingest.domain.listings import keep_tradable, tradable_listings
from stonks.ingest.domain.models import Candidates
from stonks.ingest.domain.pea import pea_countries, select_pea
from stonks.ingest.domain.universe import require_size, without_ignored
from stonks.ingest.runtime import IngestRuntime
from stonks.ingest.sources.xtrackers import SOURCE, parse_constituents

logger = logging.getLogger(__name__)


class UniverseStep:
    def __init__(self, runtime: IngestRuntime):
        self.runtime = runtime
        self.universe = runtime.settings.universe

    def execute(self, trade_date: date) -> Candidates:
        downloaded_at = datetime.now(UTC)
        constituents_csv = self.runtime.constituents.download()
        raw_key = self.runtime.store.write_constituents(SOURCE, trade_date, downloaded_at, constituents_csv)
        parsed = parse_constituents(constituents_csv)
        constituents = without_ignored(parsed, self.universe.ignored)
        countries = self.runtime.store.read_countries()
        eligible_countries = pea_countries(countries)
        listings = tradable_listings(countries)
        excluded = self.runtime.settings.pea.exclude
        pea_selection = select_pea(constituents, eligible_countries, excluded)
        selection = keep_tradable(pea_selection, listings, self.universe.symbol_overrides)
        eligible = len(selection.eligible)
        require_size(eligible, self.universe.min_instruments)
        timestamp = downloaded_at.isoformat()
        candidates = Candidates(source=SOURCE, downloaded_at=timestamp, selection=selection)
        candidates_key = self.runtime.store.write_candidates(trade_date, candidates)
        logger.info(
            "candidates_selected constituents=%d eligible=%d rejected=%d raw=%s candidates=%s",
            len(constituents),
            eligible,
            len(selection.rejections),
            raw_key,
            candidates_key,
        )
        return candidates
