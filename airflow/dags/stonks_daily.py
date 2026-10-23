from datetime import timedelta

import pendulum
from airflow.sdk import DAG
from airflow.timetables.trigger import CronTriggerTimetable
from stonks_pods import DEFAULT_ARGS, PARAMS, S3_KEYS, START_DATE, TIMEZONE, stonks_pod, stonks_spark

with DAG(
    dag_id="stonks_daily",
    description="End-of-day universe, Yahoo symbols, and Yahoo bars ingestion, then the daily Spark batch.",
    schedule=CronTriggerTimetable("45 18 * * 1-5", timezone=TIMEZONE),
    start_date=pendulum.instance(START_DATE, tz=TIMEZONE),
    catchup=False,
    max_active_runs=1,
    params=PARAMS,
    default_args=DEFAULT_ARGS,
    tags=["stonks"],
):
    universe = stonks_pod(
        "universe",
        "ingest",
        secrets=S3_KEYS,
        retries=2,
        retry_delay=timedelta(minutes=10),
        execution_timeout=timedelta(minutes=30),
    )
    symbols = stonks_pod(
        "symbols",
        "ingest",
        secrets=S3_KEYS,
        retries=2,
        retry_delay=timedelta(minutes=10),
        execution_timeout=timedelta(minutes=30),
    )
    bars = stonks_pod(
        "bars",
        "ingest",
        secrets=S3_KEYS,
        retries=3,
        retry_delay=timedelta(minutes=15),
        execution_timeout=timedelta(hours=1),
    )
    spark = stonks_spark(
        "spark",
        retries=1,
        retry_delay=timedelta(minutes=10),
        execution_timeout=timedelta(hours=1),
    )
    universe >> symbols >> bars >> spark
