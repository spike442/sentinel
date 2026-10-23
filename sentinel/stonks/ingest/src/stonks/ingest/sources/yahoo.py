from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from stonks.core.http import HttpSource, Throttle
from stonks.ingest.config.settings import YahooConfig

CHART_SOURCE = "yahoo"
SEARCH_SOURCE = "yahoo_search"
EQUITY = "EQUITY"


def equity_symbols(search_response: dict) -> list[str]:
    quotes = search_response.get("quotes") or []
    return [quote["symbol"] for quote in quotes if quote.get("quoteType") == EQUITY and quote.get("symbol")]


def epoch_seconds(day: date) -> int:
    midnight = datetime.combine(day, time.min, tzinfo=UTC)
    return int(midnight.timestamp())


def chart_result(chart_response: dict) -> dict | None:
    results = (chart_response.get("chart") or {}).get("result") or []
    return results[0] if results else None


def local_dates(result: dict, timestamps: list[int]) -> list[date]:
    zone = ZoneInfo(result["meta"]["exchangeTimezoneName"])
    return [datetime.fromtimestamp(timestamp, zone).date() for timestamp in timestamps]


def daily_closes(chart_response: dict) -> list[tuple[date, float | None]]:
    result = chart_result(chart_response)
    if result is None:
        return []
    timestamps = result.get("timestamp") or []
    quotes = (result.get("indicators") or {}).get("quote") or [{}]
    closes = quotes[0].get("close") or []
    dates = local_dates(result, timestamps)
    padded = closes + [None] * (len(dates) - len(closes))
    return list(zip(dates, padded))


def priced_dates(chart_response: dict) -> list[date]:
    closes = daily_closes(chart_response)
    return [day for day, close in closes if close is not None]


def unpriced_dates(chart_response: dict) -> list[date]:
    closes = daily_closes(chart_response)
    return [day for day, close in closes if close is None]


def split_dates(chart_response: dict) -> list[date]:
    result = chart_result(chart_response)
    if result is None:
        return []
    splits = (result.get("events") or {}).get("splits") or {}
    timestamps = [int(timestamp) for timestamp in splits]
    return local_dates(result, timestamps)


class YahooSearch:
    def __init__(self, source: HttpSource, yahoo: YahooConfig, throttle: Throttle):
        self.source = source
        self.yahoo = yahoo
        self.throttle = throttle

    def search(self, isin: str) -> dict:
        params = {"q": isin, "quotesCount": self.yahoo.quotes_count, "newsCount": 0}
        self.throttle.wait()
        response = self.source.get(self.yahoo.search_url, params)
        return response.json()


class YahooChart:
    def __init__(self, source: HttpSource, yahoo: YahooConfig, throttle: Throttle):
        self.source = source
        self.yahoo = yahoo
        self.throttle = throttle

    def daily(self, symbol: str, start: date, end: date) -> dict:
        day_after_end = end + timedelta(days=1)
        params = {
            "period1": epoch_seconds(start),
            "period2": epoch_seconds(day_after_end),
            "interval": "1d",
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
        quoted = quote(symbol, safe="")
        url = self.yahoo.chart_url.format(symbol=quoted)
        self.throttle.wait()
        response = self.source.get(url, params)
        return response.json()
