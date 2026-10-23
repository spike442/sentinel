import logging
import time

import httpx
from stonks.core.settings import HttpConfig

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def http_client(http: HttpConfig) -> httpx.Client:
    headers = {"User-Agent": http.user_agent}
    return httpx.Client(timeout=http.timeout_seconds, follow_redirects=True, headers=headers)


class Throttle:
    def __init__(self, interval_seconds: float):
        self.interval_seconds = interval_seconds
        self.last_call = float("-inf")

    def wait(self) -> None:
        elapsed = time.monotonic() - self.last_call
        remaining = self.interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self.last_call = time.monotonic()


class HttpSource:
    def __init__(self, client: httpx.Client, http: HttpConfig):
        self.client = client
        self.http = http

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.client.get(url, params=params)
            except httpx.TransportError as error:
                if attempt > self.http.max_retries:
                    raise
                self.back_off(url, attempt, type(error).__name__)
                continue
            if response.status_code in RETRYABLE_STATUSES and attempt <= self.http.max_retries:
                self.back_off(url, attempt, str(response.status_code))
                continue
            response.raise_for_status()
            return response

    def text(self, url: str) -> str:
        response = self.get(url)
        return response.text

    def back_off(self, url: str, attempt: int, cause: str) -> None:
        delay = self.http.retry_backoff_seconds * attempt
        logger.warning("http_retry url=%s attempt=%d cause=%s delay=%.1f", url, attempt, cause, delay)
        time.sleep(delay)
