from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Constituent:
    isin: str
    name: str
    currency: str
    weight: float
    main_exchange: str
    sector: str

    @property
    def country(self) -> str:
        return self.isin[:2]


@dataclass(frozen=True)
class Rejection:
    isin: str
    name: str
    reason: str


@dataclass(frozen=True)
class Selection:
    eligible: list[Constituent]
    rejections: list[Rejection]


@dataclass(frozen=True)
class Candidates:
    source: str
    downloaded_at: str
    selection: Selection


@dataclass(frozen=True)
class Instrument:
    isin: str
    symbol: str
    name: str
    country: str
    currency: str
    main_exchange: str
    sector: str
    weight: float


@dataclass(frozen=True)
class Universe:
    source: str
    downloaded_at: str
    instruments: list[Instrument]
    rejections: list[Rejection]


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    pea: bool
    exchange: str
    suffix: str


@dataclass(frozen=True)
class Listings:
    exchange_suffixes: Mapping[str, str]
    home_suffixes: Mapping[str, str]

    @property
    def suffixes(self) -> frozenset[str]:
        exchanges = set(self.exchange_suffixes.values())
        homes = set(self.home_suffixes.values())
        return frozenset(exchanges | homes)
