from datetime import date

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from stonks.spark.readers import PRICE_FIELDS

SERIES_FIELDS = (*PRICE_FIELDS, "volume")
BAR_COLUMNS = (
    "isin",
    "symbol",
    "bar_date",
    *SERIES_FIELDS,
    "currency",
    "exchange",
    "fetched_at",
)


def successful_fetches(raw: DataFrame, trade_date: date) -> DataFrame:
    fetched_by = F.to_date(F.col("trade_date").cast("string")) <= F.lit(trade_date)
    return raw.where(F.col("error").isNull() & fetched_by)


def chart_series(fetches: DataFrame) -> DataFrame:
    result = F.col("response.chart.result").getItem(0)
    quote = result["indicators"]["quote"].getItem(0)
    return fetches.select(
        "isin",
        "symbol",
        F.col("fetched_at").cast("timestamp").alias("fetched_at"),
        result["meta"]["currency"].alias("currency"),
        result["meta"]["exchangeName"].alias("exchange"),
        result["meta"]["exchangeTimezoneName"].alias("timezone"),
        result["timestamp"].alias("timestamp"),
        *[quote[name].alias(name) for name in SERIES_FIELDS],
    )


def daily_rows(series: DataFrame) -> DataFrame:
    exploded = series.select(
        "isin",
        "symbol",
        "fetched_at",
        "currency",
        "exchange",
        "timezone",
        F.explode(F.arrays_zip("timestamp", *SERIES_FIELDS)).alias("bar"),
    )
    instant = F.timestamp_seconds(F.col("bar.timestamp"))
    local_time = F.from_utc_timestamp(instant, F.col("timezone"))
    return exploded.select(
        "isin",
        "symbol",
        F.to_date(local_time).alias("bar_date"),
        F.col("bar.timestamp").alias("bar_timestamp"),
        *[F.col(f"bar.{name}").alias(name) for name in SERIES_FIELDS],
        "currency",
        "exchange",
        "fetched_at",
    )


def current_listing(rows: DataFrame, universe: DataFrame) -> DataFrame:
    listings = universe.select("isin", "symbol")
    return rows.join(listings, ["isin", "symbol"], "inner")


def newest_per_day(rows: DataFrame) -> DataFrame:
    newest_first = Window.partitionBy("isin", "bar_date").orderBy(
        F.col("fetched_at").desc(), F.col("bar_timestamp").desc()
    )
    ranked = rows.withColumn("fetch_rank", F.row_number().over(newest_first))
    return ranked.where(F.col("fetch_rank") == 1)


def yahoo_bars(raw: DataFrame, universe: DataFrame, trade_date: date) -> DataFrame:
    fetches = successful_fetches(raw, trade_date)
    series = chart_series(fetches)
    rows = daily_rows(series)
    traded = rows.where(F.col("close").isNotNull() & (F.col("bar_date") <= F.lit(trade_date)))
    listed = current_listing(traded, universe)
    newest = newest_per_day(listed)
    return newest.select(*BAR_COLUMNS)


def bars_summary(bars: DataFrame) -> dict:
    row = bars.agg(
        F.count(F.lit(1)).alias("rows"),
        F.countDistinct("isin").alias("instruments"),
        F.min("bar_date").alias("first_date"),
        F.max("bar_date").alias("last_date"),
    ).first()
    return row.asDict()
