import logging
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import httpx
from stonks.ingest.domain.bars import (
    BarWatermark,
    FetchWindow,
    advance_watermark,
    failure_ratio,
    full_window,
    needs_full_refresh,
    plan_fetch,
)
from stonks.ingest.runtime import IngestRuntime
from stonks.ingest.sources.yahoo import CHART_SOURCE, priced_dates, split_dates, unpriced_dates
from stonks.ingest.storage.store import ChartFetch

logger = logging.getLogger(__name__)


class BarsIncomplete(RuntimeError):
    pass


@dataclass(frozen=True)
class InstrumentBars:
    fetches: list[ChartFetch]
    watermark: BarWatermark | None

    @property
    def failed(self) -> bool:
        return self.watermark is None


class BarsStep:
    def __init__(self, runtime: IngestRuntime):
        self.runtime = runtime
        self.bars = runtime.settings.bars

    def execute(self, trade_date: date) -> None:
        universe = self.runtime.store.read_universe(trade_date)
        watermarks = self.runtime.store.read_watermarks()
        advanced = dict(watermarks)
        started_at = datetime.now(UTC)
        fetches = []
        attempted = 0
        failed = 0
        try:
            for instrument in universe.instruments:
                watermark = watermarks.get(instrument.isin)
                window = plan_fetch(
                    instrument,
                    watermark,
                    trade_date,
                    history_years=self.bars.history_years,
                    overlap_days=self.bars.overlap_days,
                )
                if window is None:
                    continue
                attempted += 1
                outcome = self.fetch_instrument(window, watermark, trade_date)
                fetches.extend(outcome.fetches)
                if outcome.failed:
                    failed += 1
                else:
                    advanced[instrument.isin] = outcome.watermark
        finally:
            self.record(trade_date, started_at, fetches, advanced)
        covered = len(universe.instruments) - attempted
        ratio = failure_ratio(failed, attempted)
        logger.info(
            "bars_fetched instruments=%d attempted=%d covered=%d failed=%d ratio=%.3f",
            len(universe.instruments),
            attempted,
            covered,
            failed,
            ratio,
        )
        if ratio > self.bars.max_failure_ratio:
            raise BarsIncomplete(f"{failed} of {attempted} instruments failed")

    def fetch_instrument(self, window: FetchWindow, watermark: BarWatermark | None, trade_date: date) -> InstrumentBars:
        fetch = self.fetch(window)
        if fetch.error:
            return InstrumentBars(fetches=[fetch], watermark=None)
        splits = split_dates(fetch.response)
        if needs_full_refresh(window, watermark, splits):
            logger.info("bars_split_refresh isin=%s symbol=%s splits=%s", window.isin, window.symbol, sorted(splits))
            refresh = full_window(window, watermark, self.bars.history_years)
            refreshed = self.fetch(refresh)
            if refreshed.error:
                superseded = replace(fetch, error=f"split refresh failed: {refreshed.error}")
                return InstrumentBars(fetches=[superseded, refreshed], watermark=None)
            return self.settle(refresh, watermark, [fetch, refreshed], trade_date)
        return self.settle(window, watermark, [fetch], trade_date)

    def settle(
        self, window: FetchWindow, watermark: BarWatermark | None, fetches: list[ChartFetch], trade_date: date
    ) -> InstrumentBars:
        latest = fetches[-1]
        unpriced = unpriced_dates(latest.response)
        if trade_date in unpriced:
            logger.warning("bars_unpriced isin=%s symbol=%s trade_date=%s", window.isin, window.symbol, trade_date)
            fetches[-1] = replace(latest, error="trade date bar has no prices")
            return InstrumentBars(fetches=fetches, watermark=None)
        dates = priced_dates(latest.response)
        splits = split_dates(latest.response)
        advanced = advance_watermark(watermark, window, dates, splits, trade_date)
        if advanced is None:
            logger.warning("bars_empty isin=%s symbol=%s", window.isin, window.symbol)
            fetches[-1] = replace(latest, error="no bars")
        return InstrumentBars(fetches=fetches, watermark=advanced)

    def fetch(self, window: FetchWindow) -> ChartFetch:
        fetched_at = datetime.now(UTC)
        error = None
        response = None
        try:
            response = self.runtime.chart.daily(window.symbol, window.start, window.end)
        except (httpx.HTTPError, ValueError) as failure:
            logger.warning("bars_failed isin=%s symbol=%s error=%s", window.isin, window.symbol, failure)
            error = str(failure)
        return ChartFetch(
            isin=window.isin,
            symbol=window.symbol,
            start=window.start,
            end=window.end,
            full=window.full,
            fetched_at=fetched_at,
            error=error,
            response=response,
        )

    def record(
        self, trade_date: date, started_at: datetime, fetches: list[ChartFetch], watermarks: dict[str, BarWatermark]
    ) -> None:
        if not fetches:
            return
        raw_key = self.runtime.store.write_chart_fetches(CHART_SOURCE, trade_date, started_at, fetches)
        reference_key = self.runtime.store.write_watermarks(watermarks)
        logger.info("bars_recorded fetches=%d raw=%s reference=%s", len(fetches), raw_key, reference_key)
