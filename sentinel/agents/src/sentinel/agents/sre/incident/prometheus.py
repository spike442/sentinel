import json
from typing import Any

import httpx
from langchain_core.tools import ToolException
from sentinel.agents.sre.incident.settings import PrometheusConfig
from sentinel.core.secrets import redact

MAX_QUERY_CHARS = 2000
MAX_ERROR_CHARS = 1000


def summarize(payload: dict[str, Any], max_bytes: int, known_secrets: tuple[str, ...]) -> dict[str, Any]:
    data = json.dumps(payload["data"], separators=(",", ":"), default=str)
    encoded = data.encode()
    if len(encoded) > max_bytes:
        kept = encoded[:max_bytes].decode(errors="ignore")
        data = f"{kept}… [truncated {len(encoded) - max_bytes} bytes]"
    redacted = redact(data, known_secrets)
    return {"status": payload["status"], "data": redacted, "warnings": payload.get("warnings", [])}


def rejection(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    reason = payload.get("error") if isinstance(payload, dict) else None
    detail = str(reason) if reason else response.text
    return f"Prometheus rejected the query (HTTP {response.status_code}): {detail[:MAX_ERROR_CHARS]}"


def query_prometheus(
    prometheus_url: str,
    query: str,
    start: str | None,
    end: str | None,
    step: str,
    *,
    max_bytes: int,
    known_secrets: tuple[str, ...],
) -> dict[str, Any]:
    """Run an instant or range query against the configured endpoint; never accepts an arbitrary URL.

    A rejected query or an unreachable server raises ``ToolException`` so the model sees why and can adjust.
    """
    if len(query) > MAX_QUERY_CHARS:
        raise ToolException(f"PromQL query is too long: keep it under {MAX_QUERY_CHARS} characters")
    base = prometheus_url.rstrip("/")
    if start or end:
        params = {"query": query, "step": step, **({"start": start} if start else {}), **({"end": end} if end else {})}
        url = f"{base}/api/v1/query_range"
    else:
        params, url = {"query": query}, f"{base}/api/v1/query"
    try:
        response = httpx.get(url, params=params, timeout=15)
    except httpx.HTTPError as exc:
        raise ToolException(f"Prometheus could not be reached: {type(exc).__name__}") from exc
    if response.is_error:
        reason = rejection(response)
        raise ToolException(reason)
    payload = response.json()
    return summarize(payload, max_bytes, known_secrets)


class Prometheus:
    def __init__(self, config: PrometheusConfig, max_output_bytes: int, known_secrets: tuple[str, ...]):
        self.config = config
        self.max_output_bytes = max_output_bytes
        self.known_secrets = known_secrets

    def query(self, query: str, start: str | None, end: str | None, step: str) -> dict[str, Any]:
        return query_prometheus(
            self.config.url,
            query,
            start,
            end,
            step,
            max_bytes=self.max_output_bytes,
            known_secrets=self.known_secrets,
        )
