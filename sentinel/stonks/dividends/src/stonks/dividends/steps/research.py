import logging
from datetime import UTC, date, datetime

from sentinel.agents.dividends.contracts import Security
from sentinel.core.deadline import deadline_after
from sentinel.core.observability.audit import AuditLog
from stonks.dividends.domain.models import Instrument
from stonks.dividends.domain.selection import failure_ratio, research_queue
from stonks.dividends.runtime import DividendRuntime
from stonks.dividends.storage.store import ResearchRecord

logger = logging.getLogger(__name__)


class ResearchIncomplete(RuntimeError):
    pass


def security_of(instrument: Instrument) -> Security:
    return Security(
        isin=instrument.isin,
        name=instrument.name,
        listing_symbol=instrument.symbol,
        country=instrument.country,
        main_exchange=instrument.main_exchange,
    )


class ResearchStep:
    def __init__(self, runtime: DividendRuntime):
        self.runtime = runtime
        self.research_config = runtime.settings.research

    def execute(self, trade_date: date) -> None:
        instruments = self.runtime.store.read_instruments(trade_date)
        entries = self.runtime.store.read_dividend_dates()
        queue = research_queue(
            instruments,
            entries,
            trade_date,
            recheck_days=self.research_config.recheck_days,
            limit=self.research_config.max_instruments,
        )
        started_at = datetime.now(UTC)
        records: list[ResearchRecord] = []
        try:
            for instrument in queue:
                record = self.research(instrument, trade_date)
                records.append(record)
        finally:
            self.record(trade_date, started_at, records)
        failed = sum(1 for record in records if record.error)
        ratio = failure_ratio(failed, len(queue))
        logger.info(
            "research_finished instruments=%d queued=%d failed=%d ratio=%.3f",
            len(instruments),
            len(queue),
            failed,
            ratio,
        )
        if ratio > self.research_config.max_failure_ratio:
            raise ResearchIncomplete(f"{failed} of {len(queue)} instruments failed")

    def research(self, instrument: Instrument, trade_date: date) -> ResearchRecord:
        audit = AuditLog()
        researched_at = datetime.now(UTC)
        deadline = deadline_after(researched_at, self.runtime.settings.limits.run_timeout_seconds)
        error = None
        answer = None
        try:
            security = security_of(instrument)
            result = self.runtime.agent.research(security, trade_date, audit, deadline)
            answer = result.model_dump(mode="json")
        except Exception as failure:
            logger.exception("research_failed isin=%s symbol=%s", instrument.isin, instrument.symbol)
            error = f"{type(failure).__name__}: {failure}"
            audit.record("research_failed", {"error": type(failure).__name__})
        actions = [action.model_dump(mode="json") for action in audit.actions]
        budget = audit.tool_budget.model_dump(mode="json")
        return ResearchRecord(
            isin=instrument.isin,
            symbol=instrument.symbol,
            researched_at=researched_at,
            error=error,
            answer=answer,
            audit=actions,
            tool_budget=budget,
        )

    def record(self, trade_date: date, started_at: datetime, records: list[ResearchRecord]) -> None:
        if not records:
            return
        key = self.runtime.store.write_research(trade_date, started_at, records)
        logger.info("research_recorded records=%d raw=%s", len(records), key)
