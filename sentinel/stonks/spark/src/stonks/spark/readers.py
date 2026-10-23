from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)

PRICE_FIELDS = ("open", "high", "low", "close")

QUOTE = StructType(
    [StructField(name, ArrayType(DoubleType())) for name in PRICE_FIELDS]
    + [StructField("volume", ArrayType(LongType()))]
)
META = StructType(
    [
        StructField("currency", StringType()),
        StructField("exchangeName", StringType()),
        StructField("exchangeTimezoneName", StringType()),
    ]
)
RESULT = StructType(
    [
        StructField("meta", META),
        StructField("timestamp", ArrayType(LongType())),
        StructField("indicators", StructType([StructField("quote", ArrayType(QUOTE))])),
    ]
)
CHART = StructType([StructField("result", ArrayType(RESULT))])
RAW_CHART = StructType(
    [
        StructField("isin", StringType()),
        StructField("symbol", StringType()),
        StructField("full", BooleanType()),
        StructField("fetched_at", StringType()),
        StructField("error", StringType()),
        StructField("response", StructType([StructField("chart", CHART)])),
    ]
)
INSTRUMENT = StructType(
    [
        StructField("isin", StringType()),
        StructField("symbol", StringType()),
        StructField("name", StringType()),
        StructField("country", StringType()),
        StructField("currency", StringType()),
        StructField("main_exchange", StringType()),
        StructField("sector", StringType()),
        StructField("weight", DoubleType()),
    ]
)
UNIVERSE_SNAPSHOT = StructType(
    [
        StructField("trade_date", StringType()),
        StructField("universe", StructType([StructField("instruments", ArrayType(INSTRUMENT))])),
    ]
)


def read_raw_charts(spark: SparkSession, path: str) -> DataFrame:
    return spark.read.schema(RAW_CHART).json(path)


def read_universe(spark: SparkSession, path: str) -> DataFrame:
    snapshot = spark.read.schema(UNIVERSE_SNAPSHOT).option("multiLine", "true").json(path)
    instruments = snapshot.select(F.explode("universe.instruments").alias("instrument"))
    return instruments.select("instrument.*")
