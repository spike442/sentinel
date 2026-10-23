from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class DividendStatus(StrEnum):
    CONFIRMED = "confirmed"
    DECLARED = "declared"
    UNKNOWN = "unknown"


class ExDateBasis(StrEnum):
    STATED = "stated"
    RECORD_DATE = "record_date"


@dataclass(frozen=True)
class Instrument:
    isin: str
    symbol: str
    name: str
    country: str
    main_exchange: str

    @property
    def suffix(self) -> str:
        _, dot, suffix = self.symbol.rpartition(".")
        return f".{suffix}" if dot else ""


@dataclass(frozen=True)
class Venue:
    suffix: str
    mic: str
    filing_domains: frozenset[str]


@dataclass(frozen=True)
class Evidence:
    source_url: str
    quote: str


@dataclass(frozen=True)
class Finding:
    isin: str
    announced: bool
    ex_date: date | None
    ex_date_evidence: Evidence | None
    record_date: date | None
    record_date_evidence: Evidence | None
    payment_date: date | None
    payment_date_evidence: Evidence | None
    amount: float | None
    currency: str | None
    amount_evidence: Evidence | None
    announced_on: date | None

    @property
    def evidence(self) -> tuple[Evidence, ...]:
        items = (self.ex_date_evidence, self.record_date_evidence, self.payment_date_evidence, self.amount_evidence)
        return tuple(item for item in items if item is not None)


@dataclass(frozen=True)
class Page:
    url: str
    text: str | None
    error: str | None


@dataclass(frozen=True)
class DividendDates:
    isin: str
    status: DividendStatus
    checked_on: date
    ex_date: date | None
    ex_date_basis: ExDateBasis | None
    ex_date_before: date | None
    record_date: date | None
    payment_date: date | None
    amount: float | None
    currency: str | None
    announced_on: date | None
    sources: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def horizon(self) -> date | None:
        return self.ex_date or self.ex_date_before
