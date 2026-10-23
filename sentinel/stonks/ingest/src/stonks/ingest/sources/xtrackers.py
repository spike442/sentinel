import csv
import re
from collections.abc import Mapping

from stonks.core.http import HttpSource
from stonks.ingest.domain.models import Constituent

SOURCE = "xtrackers"
DELIMITER = ";"
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
COLUMNS = {
    "isin": "Constituent ISIN",
    "name": "Constituent Name",
    "currency": "Constituent Currency ISO Code",
    "weight": "Constituent Weighting",
    "main_exchange": "Constituent Main Exchange Name",
    "sector": "Constituent Industry Classification Name",
}


class ConstituentsFormatError(ValueError):
    pass


def constituent_from_row(row: Mapping[str, str]) -> Constituent:
    weight = float(row[COLUMNS["weight"]])
    return Constituent(
        isin=row[COLUMNS["isin"]].strip(),
        name=row[COLUMNS["name"]].strip(),
        currency=row[COLUMNS["currency"]].strip(),
        weight=weight,
        main_exchange=row[COLUMNS["main_exchange"]].strip(),
        sector=row[COLUMNS["sector"]].strip(),
    )


def parse_constituents(text: str) -> list[Constituent]:
    lines = text.splitlines()
    reader = csv.DictReader(lines, delimiter=DELIMITER)
    fieldnames = set(reader.fieldnames or [])
    missing = sorted(set(COLUMNS.values()) - fieldnames)
    if missing:
        raise ConstituentsFormatError(f"constituents file is missing columns: {', '.join(missing)}")
    rows = [row for row in reader if ISIN.match(row[COLUMNS["isin"]].strip())]
    if not rows:
        raise ConstituentsFormatError("constituents file has no securities")
    return [constituent_from_row(row) for row in rows]


class XtrackersConstituents:
    def __init__(self, source: HttpSource, url: str):
        self.source = source
        self.url = url

    def download(self) -> str:
        return self.source.text(self.url)
