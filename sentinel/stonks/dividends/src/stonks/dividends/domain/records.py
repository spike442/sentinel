from datetime import date

from stonks.dividends.domain.models import DividendDates, DividendStatus, ExDateBasis, Instrument, Venue


def optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def optional_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def instrument_from_record(record: dict) -> Instrument:
    return Instrument(
        isin=record["isin"],
        symbol=record["symbol"],
        name=record["name"],
        country=record["country"],
        main_exchange=record["main_exchange"],
    )


def instruments_from_snapshot(snapshot: dict) -> list[Instrument]:
    records = snapshot["universe"]["instruments"]
    return [instrument_from_record(record) for record in records]


def venue_from_record(record: dict) -> Venue:
    filing_domains = frozenset(record["filing_domains"])
    return Venue(suffix=record["suffix"], mic=record["mic"], filing_domains=filing_domains)


def venues_from_document(document: dict) -> dict[str, Venue]:
    venues = [venue_from_record(record) for record in document.values()]
    return {venue.suffix: venue for venue in venues}


def dividend_dates_from_record(isin: str, record: dict) -> DividendDates:
    status = DividendStatus(record["status"])
    checked_on = date.fromisoformat(record["checked_on"])
    basis = ExDateBasis(record["ex_date_basis"]) if record["ex_date_basis"] else None
    ex_date = optional_date(record["ex_date"])
    ex_date_before = optional_date(record["ex_date_before"])
    record_date = optional_date(record["record_date"])
    payment_date = optional_date(record["payment_date"])
    announced_on = optional_date(record["announced_on"])
    return DividendDates(
        isin=isin,
        status=status,
        checked_on=checked_on,
        ex_date=ex_date,
        ex_date_basis=basis,
        ex_date_before=ex_date_before,
        record_date=record_date,
        payment_date=payment_date,
        amount=record["amount"],
        currency=record["currency"],
        announced_on=announced_on,
        sources=tuple(record["sources"]),
        reasons=tuple(record["reasons"]),
    )


def dividend_dates_record(entry: DividendDates) -> dict:
    return {
        "status": entry.status.value,
        "checked_on": entry.checked_on.isoformat(),
        "ex_date": optional_iso(entry.ex_date),
        "ex_date_basis": entry.ex_date_basis.value if entry.ex_date_basis else None,
        "ex_date_before": optional_iso(entry.ex_date_before),
        "record_date": optional_iso(entry.record_date),
        "payment_date": optional_iso(entry.payment_date),
        "amount": entry.amount,
        "currency": entry.currency,
        "announced_on": optional_iso(entry.announced_on),
        "sources": list(entry.sources),
        "reasons": list(entry.reasons),
    }
