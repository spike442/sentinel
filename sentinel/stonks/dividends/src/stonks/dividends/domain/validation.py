from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from stonks.dividends.domain.evidence import (
    host_of,
    issuer_host,
    mentions_amount,
    mentions_date,
    quote_found,
    under_domain,
)
from stonks.dividends.domain.models import (
    DividendDates,
    DividendStatus,
    Evidence,
    ExDateBasis,
    Finding,
    Instrument,
    Page,
)

NOT_ANNOUNCED = "no upcoming dividend announced"


@dataclass(frozen=True)
class Rules:
    newswire_domains: frozenset[str]
    issuer_domains: Mapping[str, str]
    name_stopwords: frozenset[str]
    month_names: Mapping[int, Sequence[str]]
    same_day_record_from: date


@dataclass(frozen=True)
class Check:
    instrument: Instrument
    pages: Mapping[str, Page]
    sessions: frozenset[date]
    filing_domains: frozenset[str]
    trade_date: date
    rules: Rules


def source_allowed(check: Check, url: str) -> bool:
    host = host_of(url)
    rules = check.rules
    official = rules.newswire_domains | check.filing_domains
    if under_domain(host, official):
        return True
    issuer_domain = rules.issuer_domains.get(check.instrument.isin)
    if issuer_domain:
        return under_domain(host, (issuer_domain,))
    return issuer_host(host, check.instrument.name, rules.name_stopwords)


def evidence_problems(check: Check, label: str, evidence: Evidence | None) -> list[str]:
    if evidence is None:
        return [f"{label}: no evidence"]
    allowed = source_allowed(check, evidence.source_url)
    if not allowed:
        host = host_of(evidence.source_url)
        return [f"{label}: source {host} is not an allowed source"]
    page = check.pages.get(evidence.source_url)
    if page is None or page.text is None:
        error = page.error if page else "not fetched"
        return [f"{label}: source could not be read ({error})"]
    found = quote_found(evidence.quote, page.text)
    return [] if found else [f"{label}: quote not found on {evidence.source_url}"]


def date_problems(check: Check, label: str, day: date | None, evidence: Evidence | None) -> list[str]:
    if day is None:
        return [f"{label}: not given"]
    problems = evidence_problems(check, label, evidence)
    if problems:
        return problems
    stated = mentions_date(evidence.quote, day, check.rules.month_names)
    return [] if stated else [f"{label}: quote does not state {day.isoformat()}"]


def amount_problems(check: Check, amount: float | None, evidence: Evidence | None) -> list[str]:
    if amount is None:
        return ["amount: not given"]
    problems = evidence_problems(check, "amount", evidence)
    if problems:
        return problems
    stated = mentions_amount(evidence.quote, amount)
    return [] if stated else [f"amount: quote does not state {amount}"]


def ex_date_from_record(record_date: date, sessions: frozenset[date], same_day_from: date) -> date | None:
    if record_date >= same_day_from:
        return record_date if record_date in sessions else None
    earlier = [session for session in sessions if session < record_date]
    return max(earlier) if earlier else None


def unknown(isin: str, trade_date: date, reasons: Sequence[str]) -> DividendDates:
    return DividendDates(
        isin=isin,
        status=DividendStatus.UNKNOWN,
        checked_on=trade_date,
        ex_date=None,
        ex_date_basis=None,
        ex_date_before=None,
        record_date=None,
        payment_date=None,
        amount=None,
        currency=None,
        announced_on=None,
        sources=(),
        reasons=tuple(reasons),
    )


def stated_ex_date(check: Check, finding: Finding, problems: list[str]) -> date | None:
    ex_problems = date_problems(check, "ex_date", finding.ex_date, finding.ex_date_evidence)
    problems.extend(ex_problems)
    if ex_problems:
        return None
    if finding.ex_date < check.trade_date:
        problems.append(f"ex_date: {finding.ex_date.isoformat()} has already passed")
        return None
    if finding.ex_date not in check.sessions:
        problems.append("ex_date: not a trading day on the listing exchange")
        return None
    return finding.ex_date


@dataclass(frozen=True)
class ExDecision:
    ex_date: date | None
    basis: ExDateBasis | None
    record_date: date | None


def record_ex_date(check: Check, finding: Finding, problems: list[str]) -> date | None:
    record_problems = date_problems(check, "record_date", finding.record_date, finding.record_date_evidence)
    problems.extend(record_problems)
    if record_problems:
        return None
    if finding.record_date < check.trade_date:
        problems.append(f"record_date: {finding.record_date.isoformat()} has already passed")
        return None
    derived = ex_date_from_record(finding.record_date, check.sessions, check.rules.same_day_record_from)
    if derived is None:
        problems.append("record_date: no trading day to derive the ex_date from")
    return derived


def ex_decision(check: Check, finding: Finding, problems: list[str]) -> ExDecision:
    stated = stated_ex_date(check, finding, problems)
    derived = record_ex_date(check, finding, problems)
    record_date = finding.record_date if derived else None
    if stated and derived and stated != derived:
        problems.append(f"ex_date: {stated.isoformat()} conflicts with record_date rule ({derived.isoformat()})")
        return ExDecision(ex_date=None, basis=None, record_date=None)
    if stated:
        return ExDecision(ex_date=stated, basis=ExDateBasis.STATED, record_date=record_date)
    if derived:
        return ExDecision(ex_date=derived, basis=ExDateBasis.RECORD_DATE, record_date=record_date)
    return ExDecision(ex_date=None, basis=None, record_date=None)


def timely(check: Check, decision: ExDecision, payment_date: date | None, problems: list[str]) -> ExDecision:
    ex_date = decision.ex_date
    if ex_date and ex_date < check.trade_date:
        problems.append(f"ex_date: {ex_date.isoformat()} has already passed")
        return ExDecision(ex_date=None, basis=None, record_date=None)
    if ex_date and payment_date and payment_date < ex_date:
        problems.append("payment_date: before the ex_date")
        return ExDecision(ex_date=None, basis=None, record_date=None)
    return decision


def validate(check: Check, finding: Finding) -> DividendDates:
    if not finding.announced:
        return unknown(finding.isin, check.trade_date, [NOT_ANNOUNCED])
    problems: list[str] = []
    decision = ex_decision(check, finding, problems)
    payment_problems = date_problems(check, "payment_date", finding.payment_date, finding.payment_date_evidence)
    problems.extend(payment_problems)
    payment_date = None if payment_problems else finding.payment_date
    amount_issues = amount_problems(check, finding.amount, finding.amount_evidence)
    problems.extend(amount_issues)
    amount = None if amount_issues else finding.amount
    decision = timely(check, decision, payment_date, problems)
    if decision.ex_date:
        status = DividendStatus.CONFIRMED
        ex_date_before = None
    elif payment_date and payment_date > check.trade_date and amount is not None:
        status = DividendStatus.DECLARED
        ex_date_before = payment_date
    else:
        return unknown(finding.isin, check.trade_date, problems)
    accepted = accepted_sources(finding, decision, payment_date=payment_date, amount=amount)
    return DividendDates(
        isin=finding.isin,
        status=status,
        checked_on=check.trade_date,
        ex_date=decision.ex_date,
        ex_date_basis=decision.basis,
        ex_date_before=ex_date_before,
        record_date=decision.record_date,
        payment_date=payment_date,
        amount=amount,
        currency=finding.currency if amount is not None else None,
        announced_on=finding.announced_on,
        sources=accepted,
        reasons=tuple(problems),
    )


def accepted_sources(
    finding: Finding, decision: ExDecision, *, payment_date: date | None, amount: float | None
) -> tuple[str, ...]:
    candidates = [
        finding.ex_date_evidence if decision.basis is ExDateBasis.STATED else None,
        finding.record_date_evidence if decision.record_date else None,
        finding.payment_date_evidence if payment_date else None,
        finding.amount_evidence if amount is not None else None,
    ]
    urls = {evidence.source_url for evidence in candidates if evidence is not None}
    return tuple(sorted(urls))


def settled(previous: DividendDates | None, verdict: DividendDates, trade_date: date) -> DividendDates:
    if verdict.status is not DividendStatus.UNKNOWN or previous is None:
        return verdict
    horizon = previous.horizon
    if previous.status is DividendStatus.UNKNOWN or horizon is None or horizon < trade_date:
        return verdict
    return replace(previous, checked_on=verdict.checked_on, reasons=verdict.reasons)
