import json
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from stonks.core.settings import S3Config, StonksSettings

MISSING_KEY_CODES = ("NoSuchKey", "404")


def s3_client(settings: StonksSettings):
    addressing = Config(s3={"addressing_style": "path"})
    return boto3.client(
        "s3",
        endpoint_url=settings.s3.endpoint,
        region_name=settings.s3.region,
        aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        config=addressing,
    )


def is_missing(error: ClientError) -> bool:
    return error.response["Error"]["Code"] in MISSING_KEY_CODES


def stamped(stem: str, at: datetime, extension: str) -> str:
    stamp = at.strftime("%Y%m%dT%H%M%SZ")
    return f"{stem}-{stamp}.{extension}"


def json_lines(records: list[dict]) -> str:
    lines = [json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records]
    return "\n".join(lines)


def parse_json_lines(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class ObjectStore:
    def __init__(self, client, s3: S3Config):
        self.client = client
        self.bucket = s3.bucket

    def put_text(self, key: str, body: str, content_type: str) -> str:
        encoded = body.encode()
        self.client.put_object(Bucket=self.bucket, Key=key, Body=encoded, ContentType=content_type)
        return key

    def put_json(self, key: str, document: dict) -> str:
        body = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
        return self.put_text(key, body, "application/json")

    def put_json_lines(self, key: str, records: list[dict]) -> str:
        body = json_lines(records)
        return self.put_text(key, body, "application/x-ndjson")

    def get_text(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        with response["Body"] as body:
            content = body.read()
        return content.decode("utf-8")

    def find_text(self, key: str) -> str | None:
        try:
            return self.get_text(key)
        except ClientError as error:
            if is_missing(error):
                return None
            raise

    def find_json(self, key: str) -> dict | None:
        text = self.find_text(key)
        return None if text is None else json.loads(text)

    def require_json(self, key: str, missing: type[LookupError], hint: str) -> dict:
        document = self.find_json(key)
        if document is None:
            raise missing(f"no object at {key}; {hint}")
        return document

    def keys(self, prefix: str) -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
        found = [item["Key"] for page in pages for item in page.get("Contents", [])]
        return sorted(found)
