from pyspark.sql import DataFrame, SparkSession


def escape_jaas(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def read_stream(spark: SparkSession, config: dict, username: str, password: str, group_id: str) -> DataFrame:
    streaming = config["streaming"]
    kafka = config["kafka"]
    jaas = (
        "org.apache.kafka.common.security.scram.ScramLoginModule required "
        f'username="{escape_jaas(username)}" '
        f'password="{escape_jaas(password)}";'
    )
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka["bootstrap_servers"])
        .option("subscribe", ",".join(streaming["topics"]))
        .option("kafka.group.id", group_id)
        .option("kafka.security.protocol", kafka["security_protocol"])
        .option("kafka.sasl.mechanism", kafka["sasl_mechanisms"])
        .option("kafka.sasl.jaas.config", jaas)
        .option("startingOffsets", streaming["starting_offsets"])
        .option("maxOffsetsPerTrigger", streaming["max_offsets_per_trigger"])
        .option("failOnDataLoss", "false")
        .load()
    )
