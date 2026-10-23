from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

Rows = list[dict[str, Any]]


class Area(StrEnum):
    UNIVERSE = "universe"
    REFERENCE = "reference"


def keyed_rows(document: dict[str, Any], key: str) -> Rows:
    return [
        {key: name, **value} if isinstance(value, dict) else {key: name, "value": value}
        for name, value in document.items()
    ]


def universe_instruments(document: dict[str, Any]) -> Rows:
    return document["universe"]["instruments"]


def universe_rejections(document: dict[str, Any]) -> Rows:
    return document["universe"]["rejections"]


def candidates(document: dict[str, Any]) -> Rows:
    return document["candidates"]["eligible"]


def by_isin(document: dict[str, Any]) -> Rows:
    return keyed_rows(document, "isin")


def by_country(document: dict[str, Any]) -> Rows:
    return keyed_rows(document, "code")


@dataclass(frozen=True)
class Dataset:
    name: str
    label: str
    area: Area
    document: str
    rows: Callable[[dict[str, Any]], Rows]

    @property
    def trade_dated(self) -> bool:
        return self.area is Area.UNIVERSE


DATASETS = {
    dataset.name: dataset
    for dataset in (
        Dataset("universe", "Universe", Area.UNIVERSE, "universe.json", universe_instruments),
        Dataset("rejections", "Rejections", Area.UNIVERSE, "universe.json", universe_rejections),
        Dataset("candidates", "Candidates", Area.UNIVERSE, "candidates.json", candidates),
        Dataset("dividends", "Dividend dates", Area.REFERENCE, "dividend-dates.json", by_isin),
        Dataset("bar-watermarks", "Bar watermarks", Area.REFERENCE, "yahoo-bar-watermarks.json", by_isin),
        Dataset("symbols", "Yahoo symbols", Area.REFERENCE, "yahoo-symbols.json", by_isin),
        Dataset("countries", "Countries", Area.REFERENCE, "countries.json", by_country),
    )
}


def columns(rows: Rows) -> list[str]:
    names: dict[str, None] = {}
    for row in rows:
        names.update(dict.fromkeys(row))
    return list(names)
