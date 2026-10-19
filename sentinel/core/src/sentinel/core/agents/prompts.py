from sentinel.core.config.settings import S3ServiceConfig
from sentinel.core.s3 import s3_client


class PromptStore:
    def __init__(self, s3: S3ServiceConfig, access_key_id: str, secret_access_key: str) -> None:
        self.bucket = s3.bucket
        self.s3_client = s3_client(s3, access_key_id, secret_access_key)
        self._cache: dict[str, str] = {}

    def load_text(self, repository: str, agent: str, name: str) -> str:
        key = f"context/{repository}/prompts/{agent}/{name}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
        with response["Body"] as body:
            content = body.read()
        text = content.decode("utf-8")
        self._cache[key] = text
        return text

    def close(self) -> None:
        self.s3_client.close()
