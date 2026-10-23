import logging
from collections import Counter
from datetime import date

import httpx
from sentinel.agents.dividends.contracts import DividendAnswer, SourceQuote
from stonks.dividends.domain.models import DividendDates, Evidence, Finding, Instrument, Page
from stonks.dividends.domain.validation import Check, Rules, settled, validate
from stonks.dividends.runtime import DividendRuntime
from stonks.dividends.sources.venues import ListingVenues
from stonks.dividends.storage.store import ResearchRecord

logger = logging.getLogger(__name__)


def evidence_from_quote(quote: SourceQuote | None) -> Evidence | None:
    if quote is None:
        return None
    return Evidence(source_url=quote.source_url, quote=quote.quote)


def finding_from_answer(isin: str, answer: DividendAnswer) -> Finding:
    ex_date_evidence = evidence_from_quote(answer.ex_date_evidence)
    record_date_evidence = evidence_from_quote(answer.record_date_evidence)
    payment_date_evidence = evidence_from_quote(answer.payment_date_evidence)
    amount_evidence = evidence_from_quote(answer.amount_evidence)
    return Finding(
        isin=isin,
        announced=answer.announced,
        ex_date=answer.ex_date,
        ex_date_evidence=ex_date_evidence,
        record_date=answer.record_date,
        record_date_evidence=record_date_evidence,
        payment_date=answer.payment_date,
        payment_date_evidence=payment_date_evidence,
        amount=answer.amount,
        currency=answer.currency,
        amount_evidence=amount_evidence,
        announced_on=answer.announced_on,
    )


def newest_per_isin(records: list[ResearchRecord]) -> dict[str, ResearchRecord]:
    ordered = sorted(records, key=lambda record: record.researched_at)
    return {record.isin: record for record in ordered}


class ValidateStep:
    def __init__(self, runtime: DividendRuntime):
        self.runtime = runtime
        validation = runtime.settings.validation
        self.days_ahead = validation.calendar_days_ahead
        self.rules = Rules(
            newswire_domains=validation.newswire_domains,
            issuer_domains=validation.issuer_domains,
            name_stopwords=validation.name_stopwords,
            month_names=validation.month_names,
            same_day_record_from=validation.same_day_record_from,
        )

    def execute(self, trade_date: date) -> None:
        store = self.runtime.store
        records = store.read_research(trade_date)
        newest = newest_per_isin(records)
        instruments = store.read_instruments(trade_date)
        listed = {instrument.isin: instrument for instrument in instruments}
        entries = store.read_dividend_dates()
        venue_records = store.read_venues()
        venues = ListingVenues(venue_records, self.days_ahead)
        statuses: Counter[str] = Counter()
        for isin, record in newest.items():
            instrument = listed.get(isin)
            if record.error or record.answer is None or instrument is None:
                statuses["skipped"] += 1
                continue
            verdict = self.verdict(instrument, record, venues, trade_date)
            previous = entries.get(isin)
            entry = settled(previous, verdict, trade_date)
            entries[isin] = entry
            statuses[entry.status.value] += 1
            reasons = "; ".join(entry.reasons)
            logger.info(
                "dividend_validated isin=%s status=%s ex_date=%s reasons=%s",
                isin,
                entry.status.value,
                entry.ex_date,
                reasons,
            )
        key = store.write_dividend_dates(entries)
        logger.info("dividends_recorded researched=%d statuses=%s reference=%s", len(newest), dict(statuses), key)

    def verdict(
        self, instrument: Instrument, record: ResearchRecord, venues: ListingVenues, trade_date: date
    ) -> DividendDates:
        answer = DividendAnswer.model_validate(record.answer)
        finding = finding_from_answer(instrument.isin, answer)
        pages = self.pages(finding)
        sessions = venues.sessions(instrument.suffix, trade_date)
        filing_domains = venues.filing_domains(instrument.suffix)
        check = Check(
            instrument=instrument,
            pages=pages,
            sessions=sessions,
            filing_domains=filing_domains,
            trade_date=trade_date,
            rules=self.rules,
        )
        return validate(check, finding)

    def pages(self, finding: Finding) -> dict[str, Page]:
        urls = {evidence.source_url for evidence in finding.evidence}
        return {url: self.page(url) for url in sorted(urls)}

    def page(self, url: str) -> Page:
        try:
            text = self.runtime.reader.read(url)
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("source_unreadable url=%s error=%s", url, error)
            return Page(url=url, text=None, error=str(error))
        return Page(url=url, text=text, error=None)
