from collections.abc import Collection, Mapping, Sequence

from stonks.ingest.domain.models import Constituent, Country, Listings, Selection


def symbol_suffix(symbol: str) -> str:
    _, dot, suffix = symbol.rpartition(".")
    return f".{suffix}" if dot else ""


def preferred_suffixes(constituent: Constituent, listings: Listings) -> list[str]:
    candidates = [
        listings.exchange_suffixes.get(constituent.main_exchange),
        listings.home_suffixes.get(constituent.country),
    ]
    return [suffix for suffix in candidates if suffix]


def choose_symbol(symbols: Sequence[str], preferred: Sequence[str], allowed: Collection[str]) -> str | None:
    listed = [symbol for symbol in symbols if symbol_suffix(symbol) in allowed]
    for suffix in preferred:
        matching = [symbol for symbol in listed if symbol_suffix(symbol) == suffix]
        if matching:
            return matching[0]
    return listed[0] if listed else None


def needs_lookup(constituent: Constituent, known: Mapping[str, str], overrides: Mapping[str, str]) -> bool:
    return constituent.isin not in known and constituent.isin not in overrides


def resolved_symbol(constituent: Constituent, known: Mapping[str, str], overrides: Mapping[str, str]) -> str | None:
    override = overrides.get(constituent.isin)
    return override or known.get(constituent.isin)


def listing_suffix(constituent: Constituent, listings: Listings, overrides: Mapping[str, str]) -> str | None:
    override = overrides.get(constituent.isin)
    if override:
        return symbol_suffix(override)
    if constituent.main_exchange:
        return listings.exchange_suffixes.get(constituent.main_exchange)
    return listings.home_suffixes.get(constituent.country)


def is_tradable(constituent: Constituent, listings: Listings, overrides: Mapping[str, str]) -> bool:
    suffix = listing_suffix(constituent, listings, overrides)
    return suffix in listings.suffixes


def keep_tradable(selection: Selection, listings: Listings, overrides: Mapping[str, str]) -> Selection:
    eligible = [constituent for constituent in selection.eligible if is_tradable(constituent, listings, overrides)]
    return Selection(eligible=eligible, rejections=selection.rejections)


def tradable_listings(countries: Mapping[str, Country]) -> Listings:
    eligible = [country for country in countries.values() if country.pea]
    exchange_suffixes = {country.exchange: country.suffix for country in eligible}
    home_suffixes = {country.code: country.suffix for country in eligible}
    return Listings(exchange_suffixes=exchange_suffixes, home_suffixes=home_suffixes)
