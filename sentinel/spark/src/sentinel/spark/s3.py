import json
import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config as BotoConfig


def create_client(s3: dict):
    return boto3.client(
        "s3",
        endpoint_url=s3["endpoint"],
        region_name=s3["region"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


def write_row(client, streaming: dict, s3: dict, row, outcome: dict) -> None:
    prefix = streaming["raw_prefix"].rstrip("/")
    timestamp = row.timestamp.replace(tzinfo=timezone.utc)
    domain = outcome["domain"]
    record = {
        "event_id": outcome["workflow_id"],
        "domain": domain,
        "topic": row.topic,
        "partition": row.partition,
        "offset": row.offset,
        "payload": outcome,
        "kafka_timestamp": timestamp.isoformat(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    run_date = outcome["record"]["updated_at"][:10]
    key = (
        f"{prefix}/domain={domain}/run_date={run_date}/workflow_id={outcome['workflow_id']}"
        f"/{row.partition:04d}-{row.offset:012d}.jsonl"
    )
    client.put_object(
        Bucket=s3["bucket"],
        Key=key,
        Body=f"{json.dumps(record, separators=(',', ':'), ensure_ascii=False)}\n".encode(),
        ContentType="application/x-ndjson",
    )
