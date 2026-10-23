import runpy
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

CHART_CONFIG = Path(__file__).parents[4] / "infra" / "chart" / "stonks" / "config"


def test_spark_job_reads_yahoo_bars_and_stops_its_session(monkeypatch, tmp_path) -> None:
    shutil.copy(CHART_CONFIG / "common" / "logging.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "common" / "storage.yaml", tmp_path)
    (tmp_path / "s3.yaml").write_text("s3:\n  endpoint: http://s3.test\n  region: us-east-1\n  bucket: stonks\n")
    monkeypatch.setenv("STONKS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    from stonks.spark import main

    spark = MagicMock()
    pyspark_sql = ModuleType("pyspark.sql")
    pyspark_sql.SparkSession = SimpleNamespace(builder=MagicMock())
    pyspark_sql.SparkSession.builder.appName.return_value.config.return_value.getOrCreate.return_value = spark
    readers = ModuleType("stonks.spark.readers")
    readers.read_raw_charts = MagicMock()
    readers.read_universe = MagicMock()
    bars = ModuleType("stonks.spark.bars")
    bars.yahoo_bars = MagicMock()
    bars.bars_summary = MagicMock(return_value={"rows": 1, "instruments": 1, "first_date": None, "last_date": None})
    monkeypatch.setitem(sys.modules, "pyspark", ModuleType("pyspark"))
    monkeypatch.setitem(sys.modules, "pyspark.sql", pyspark_sql)
    monkeypatch.setitem(sys.modules, "stonks.spark.readers", readers)
    monkeypatch.setitem(sys.modules, "stonks.spark.bars", bars)
    monkeypatch.delitem(sys.modules, "stonks.spark.daily", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--trade-date", "2026-10-21"])

    runpy.run_path(main.__file__, run_name="__main__")

    pyspark_sql.SparkSession.builder.appName.assert_called_once_with("stonks-daily")
    readers.read_raw_charts.assert_called_once_with(spark, "s3a://stonks/raw/source=yahoo")
    readers.read_universe.assert_called_once_with(spark, "s3a://stonks/universe/trade_date=2026-10-21/universe.json")
    bars.bars_summary.assert_called_once()
    spark.stop.assert_called_once()
