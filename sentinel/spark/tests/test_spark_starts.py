import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock


def test_spark_job_starts_its_stream(monkeypatch) -> None:
    from sentinel.spark import main

    spark = MagicMock()
    pyspark_sql = ModuleType("pyspark.sql")
    pyspark_sql.SparkSession = SimpleNamespace(builder=MagicMock())
    pyspark_sql.SparkSession.builder.appName.return_value.config.return_value.getOrCreate.return_value = spark
    kafka = ModuleType("sentinel.spark.kafka")
    records = MagicMock()
    kafka.read_stream = MagicMock(return_value=records)
    monkeypatch.setitem(sys.modules, "pyspark", ModuleType("pyspark"))
    monkeypatch.setitem(sys.modules, "pyspark.sql", pyspark_sql)
    monkeypatch.setitem(sys.modules, "sentinel.spark.kafka", kafka)
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")

    runpy.run_path(main.__file__, run_name="__main__")

    records.writeStream.foreachBatch.assert_called_once()
    spark.streams.awaitAnyTermination.assert_called_once()
    spark.stop.assert_called_once()
