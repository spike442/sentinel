import re
from datetime import date

from stonks.api.datasets import Area, Dataset
from stonks.core.objects import ObjectStore
from stonks.core.settings import StorageConfig

TRADE_DATE = re.compile(r"trade_date=(\d{4}-\d{2}-\d{2})/universe\.json$")


class StonksReader:
    def __init__(self, objects: ObjectStore, storage: StorageConfig):
        self.objects = objects
        self.universe_prefix = storage.universe_prefix.rstrip("/")
        self.reference_prefix = storage.reference_prefix.rstrip("/")

    def trade_dates(self) -> list[date]:
        keys = self.objects.keys(f"{self.universe_prefix}/")
        found = {match.group(1) for key in keys if (match := TRADE_DATE.search(key))}
        days = [date.fromisoformat(day) for day in found]
        return sorted(days, reverse=True)

    def document(self, dataset: Dataset, trade_date: date | None) -> dict | None:
        if dataset.area is Area.UNIVERSE:
            key = f"{self.universe_prefix}/trade_date={trade_date.isoformat()}/{dataset.document}"
        else:
            key = f"{self.reference_prefix}/{dataset.document}"
        return self.objects.find_json(key)
