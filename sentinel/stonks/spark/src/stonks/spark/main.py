import argparse
import logging
from collections.abc import Sequence
from datetime import date

from stonks.spark.config import load_config
from stonks.spark.s3 import s3a_options


def parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="stonks-spark")
    parser.add_argument("--trade-date", required=True, type=date.fromisoformat)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    from pyspark.sql import SparkSession
    from stonks.spark.daily import run_daily

    arguments = parse_arguments(argv)
    config = load_config()
    logging.basicConfig(level=config["logging"]["level"])
    options = {"spark.sql.session.timeZone": "UTC", **s3a_options(config["s3"])}
    spark = SparkSession.builder.appName("stonks-daily").config(map=options).getOrCreate()
    try:
        run_daily(spark, arguments.trade_date, config["storage"], config["s3"])
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
