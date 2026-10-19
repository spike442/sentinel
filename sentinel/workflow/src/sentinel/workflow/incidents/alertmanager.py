import httpx
from sentinel.core.contracts.incidents import Alert


class AlertmanagerClient:
    def __init__(self, url: str):
        self.client = httpx.Client(base_url=url, timeout=10)

    def is_firing(self, alert: Alert) -> bool:
        alertname = alert.labels.get("alertname")
        params = {"filter": f'alertname="{alertname}"'} if alertname else {}
        response = self.client.get("/api/v2/alerts", params=params)
        response.raise_for_status()
        alerts = response.json()
        fingerprints = {item.get("fingerprint") for item in alerts}
        return alert.fingerprint in fingerprints

    def close(self) -> None:
        self.client.close()
