import httpx
from pydantic import SecretStr
from sentinel.core.observability.logging import redact_logged_secrets

DISCORD_MESSAGE_LIMIT = 2000


class DiscordRejected(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"Discord rejected the notification: HTTP {status_code}")


class DiscordWebhook:
    def __init__(self, url: SecretStr):
        self.url = url.get_secret_value()
        redact_logged_secrets("httpx", [self.url])
        self.client = httpx.Client(timeout=15)

    def post(self, text: str) -> int:
        content = text[:DISCORD_MESSAGE_LIMIT]
        response = self.client.post(self.url, json={"content": content, "allowed_mentions": {"parse": []}})
        if response.is_error:
            raise DiscordRejected(response.status_code)
        return response.status_code

    def close(self) -> None:
        self.client.close()
