import io
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

INFRA = Path(__file__).parents[4] / "infra"
CHART_CONFIG = INFRA / "chart" / "stonks" / "config"
PROMPTS = INFRA / "context" / "stonks" / "prompts"
COUNTRIES = INFRA / "reference" / "stonks" / "countries.json"
SOURCE = "https://totalenergies.com/news/press-releases/second-interim-dividend-2026"
QUOTE = "The second interim dividend of 0.90 euro per share will go ex-dividend on December 31, 2026."
PAGE = f"<html><body><p>Dividend</p><p>{QUOTE}</p><p>It will be paid on January 5, 2027.</p></body></html>"
UNIVERSE = {
    "trade_date": "2026-10-21",
    "universe": {
        "instruments": [
            {
                "isin": "FR0000120271",
                "symbol": "TTE.PA",
                "name": "TOTALENERGIES",
                "country": "FR",
                "currency": "EUR",
                "main_exchange": "Euronext Paris",
                "sector": "Energy",
                "weight": 0.002,
            }
        ]
    },
}


class MemoryS3:
    def __init__(self):
        self.objects = {}
        self.closed = False

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def get_paginator(self, name):
        paginator = MagicMock()
        paginator.paginate.side_effect = lambda Bucket, Prefix: [
            {"Contents": [{"Key": key} for key in self.objects if key.startswith(Prefix)]}
        ]
        return paginator

    def close(self):
        self.closed = True


def http_response(url, params=None):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/html; charset=utf-8"}
    response.text = PAGE
    response.content = PAGE.encode()
    return response


def test_dividend_steps_start_and_close_their_runtime(monkeypatch, tmp_path) -> None:
    shutil.copy(CHART_CONFIG / "common" / "logging.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "common" / "llm.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "common" / "storage.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "dividends.yaml", tmp_path)
    (tmp_path / "s3.yaml").write_text("s3:\n  endpoint: http://s3.test\n  region: us-east-1\n  bucket: stonks\n")
    monkeypatch.setenv("STONKS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("LLM_API_KEY", "test")
    from sentinel.agents.dividends.contracts import DividendAnswer
    from sentinel.agents.framework import runner as agent_runner

    from stonks.core import http, objects
    from stonks.dividends import main

    storage = MemoryS3()
    storage.objects["universe/trade_date=2026-10-21/universe.json"] = json.dumps(UNIVERSE).encode()
    storage.objects["reference/countries.json"] = COUNTRIES.read_bytes()
    for prompt in PROMPTS.rglob("*.md"):
        relative = prompt.relative_to(INFRA / "context")
        storage.objects[f"context/{relative}"] = prompt.read_bytes()
    monkeypatch.setattr(objects.boto3, "client", MagicMock(return_value=storage))
    client = MagicMock()
    client.get.side_effect = http_response
    monkeypatch.setattr(http.httpx, "Client", MagicMock(return_value=client))
    model = MagicMock()
    monkeypatch.setattr(agent_runner, "chat_model", MagicMock(return_value=model))
    evidence = {"source_url": SOURCE, "quote": QUOTE}
    answer = DividendAnswer(
        announced=True,
        ex_date="2026-12-31",
        ex_date_evidence=evidence,
        record_date=None,
        record_date_evidence=None,
        payment_date=None,
        payment_date_evidence=None,
        amount=0.90,
        currency="EUR",
        amount_evidence=evidence,
        announced_on="2026-07-22",
        summary="Second interim dividend for fiscal year 2026.",
    )
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [], "structured_response": answer}
    structured_agent = MagicMock(return_value=agent)
    monkeypatch.setattr(agent_runner, "structured_agent", structured_agent)

    main.main(["research", "--trade-date", "2026-10-21"])
    main.main(["validate", "--trade-date", "2026-10-21"])

    assert any(key.startswith("raw/source=dividend_agent/trade_date=2026-10-21/research-") for key in storage.objects)
    assert "reference/dividend-dates.json" in storage.objects
    assert "Research instructions" in structured_agent.call_args.kwargs["system_prompt"]
    assert model.root_client.close.call_count == 2
    assert client.close.call_count == 2
    assert storage.closed
