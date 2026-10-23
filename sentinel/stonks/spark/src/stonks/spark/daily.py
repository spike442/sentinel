import logging
from datetime import date

from stonks.spark.bars import bars_summary, yahoo_bars
from stonks.spark.readers import read_raw_charts, read_universe

logger = logging.getLogger(__name__)

YAHOO = "yahoo"


def raw_source_path(storage: dict, s3: dict, source: str) -> str:
    prefix = storage["raw_prefix"].rstrip("/")
    return f"s3a://{s3['bucket']}/{prefix}/source={source}"


def universe_path(storage: dict, s3: dict, trade_date: date) -> str:
    prefix = storage["universe_prefix"].rstrip("/")
    return f"s3a://{s3['bucket']}/{prefix}/trade_date={trade_date.isoformat()}/universe.json"


def run_daily(spark, trade_date: date, storage: dict, s3: dict) -> None:
    charts_path = raw_source_path(storage, s3, YAHOO)
    snapshot_path = universe_path(storage, s3, trade_date)
    raw = read_raw_charts(spark, charts_path)
    universe = read_universe(spark, snapshot_path)
    bars = yahoo_bars(raw, universe, trade_date)
    summary = bars_summary(bars)
    logger.info(
        "yahoo_bars trade_date=%s rows=%s instruments=%s first_date=%s last_date=%s charts=%s universe=%s",
        trade_date,
        summary["rows"],
        summary["instruments"],
        summary["first_date"],
        summary["last_date"],
        charts_path,
        snapshot_path,
    )
