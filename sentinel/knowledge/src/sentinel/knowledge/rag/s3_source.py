from collections.abc import Iterator

from sentinel.core.config.settings import S3ServiceConfig
from sentinel.core.s3 import s3_client
from sentinel.knowledge.config import RagSourceConfig


class S3KnowledgeSource:
    def __init__(self, config: S3ServiceConfig, source: RagSourceConfig, access_key_id: str, secret_access_key: str):
        self.source = source
        self.client = s3_client(config, access_key_id, secret_access_key)
        self.bucket = config.bucket

    def list_objects(self) -> Iterator[tuple[str, str]]:
        prefix = f"context/{self.source.repository}/knowledge/"
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        for item in response.get("Contents", []):
            key = item["Key"]
            if not key.endswith("/"):
                yield key, item["ETag"].strip('"')

    def read_object(self, key: str) -> str:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        with response["Body"] as body:
            return body.read().decode("utf-8")

    def close(self) -> None:
        self.client.close()
