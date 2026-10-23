class PromptStore:
    """Agent prompts read once per process from ``context/<scope>/prompts/<agent>/<name>`` in one bucket.

    The scope is what the prompts are written for: a Sentinel repository, or a domain such as ``stonks``.
    The caller owns the S3 client and closes it.
    """

    def __init__(self, client, bucket: str) -> None:
        self.client = client
        self.bucket = bucket
        self._cache: dict[str, str] = {}

    def load_text(self, scope: str, agent: str, name: str) -> str:
        key = f"context/{scope}/prompts/{agent}/{name}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        with response["Body"] as body:
            content = body.read()
        text = content.decode("utf-8")
        self._cache[key] = text
        return text
