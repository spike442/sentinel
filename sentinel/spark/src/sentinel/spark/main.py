import json
import logging
import os

from sentinel.spark.config import load_config
from sentinel.spark.s3 import create_client, write_row

logger = logging.getLogger(__name__)


def process_partition(rows, streaming: dict, s3: dict) -> None:
    client = create_client(s3)
    try:
        for row in rows:
            outcome = json.loads(row.value)
            write_row(client, streaming, s3, row, outcome)
            logger.info(
                "workflow_outcome domain=%s workflow_id=%s status=%s",
                outcome["domain"],
                outcome["workflow_id"],
                outcome["record"]["status"],
            )
    finally:
        client.close()


def process_batch(batch, _batch_id: int, streaming: dict, s3: dict) -> None:
    batch.select("topic", "partition", "offset", "value", "timestamp").foreachPartition(
        lambda rows: process_partition(rows, streaming, s3)
    )


def main() -> None:
    from pyspark.sql import SparkSession
    from sentinel.spark.kafka import read_stream

    config = load_config()
    logging.basicConfig(level=config["logging"]["level"])
    streaming = config["streaming"]
    s3 = config["s3"]
    spark = SparkSession.builder.appName("sentinel-spark").config("spark.sql.session.timeZone", "UTC").getOrCreate()
    try:
        records = read_stream(
            spark,
            config,
            os.environ["SENTINEL_KAFKA_USERNAME"],
            os.environ["SENTINEL_KAFKA_PASSWORD"],
            streaming["consumer_group"],
        )
        (
            records.writeStream.foreachBatch(lambda batch, batch_id: process_batch(batch, batch_id, streaming, s3))
            .queryName("sentinel-workflow-outcomes")
            .outputMode("append")
            .option("checkpointLocation", streaming["checkpoint"])
            .trigger(processingTime=streaming["trigger_interval"])
            .start()
        )
        spark.streams.awaitAnyTermination()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
