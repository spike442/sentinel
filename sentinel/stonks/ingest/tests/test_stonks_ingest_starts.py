import io
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

CHART_CONFIG = Path(__file__).parents[4] / "infra" / "chart" / "stonks" / "config"
COUNTRIES = Path(__file__).parents[4] / "infra" / "reference" / "stonks" / "countries.json"
CONSTITUENTS = (
    "ShareClass ISIN;Constituent ISIN;Constituent Name;Constituent Country;Constituent Currency ISO Code;"
    "Constituent Weighting;Constituent Rating;Constituent Main Exchange Name;Constituent Industry Classification Name\n"
    "LU0328475792;DE0007164600;SAP;Germany;EUR;0.0152;A2;XETRA;Technology\n"
)
SEARCH = {"quotes": [{"symbol": "SAP.DE", "quoteType": "EQUITY"}]}
CHART = {
    "chart": {
        "result": [
            {
                "meta": {"currency": "EUR", "exchangeTimezoneName": "Europe/Berlin"},
                "timestamp": [1792566000],
                "indicators": {"quote": [{"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]}]},
            }
        ]
    }
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

    def close(self):
        self.closed = True


def http_response(url, params=None):
    response = MagicMock()
    response.status_code = 200
    response.text = CONSTITUENTS
    response.json.return_value = CHART if "/chart/" in url else SEARCH
    return response


def test_ingest_steps_start_and_close_their_runtime(monkeypatch, tmp_path) -> None:
    shutil.copy(CHART_CONFIG / "common" / "logging.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "common" / "storage.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "ingest.yaml", tmp_path)
    (tmp_path / "s3.yaml").write_text("s3:\n  endpoint: http://s3.test\n  region: us-east-1\n  bucket: stonks\n")
    monkeypatch.setenv("STONKS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("INGEST_UNIVERSE__MIN_INSTRUMENTS", "1")
    from stonks.core import http, objects
    from stonks.ingest import main

    storage = MemoryS3()
    storage.objects["reference/countries.json"] = COUNTRIES.read_bytes()
    monkeypatch.setattr(objects.boto3, "client", MagicMock(return_value=storage))
    client = MagicMock()
    client.get.side_effect = http_response
    monkeypatch.setattr(http.httpx, "Client", MagicMock(return_value=client))

    main.main(["universe", "--trade-date", "2026-10-21"])
    main.main(["symbols", "--trade-date", "2026-10-21"])
    main.main(["bars", "--trade-date", "2026-10-21"])

    assert any(key.startswith("raw/source=xtrackers/trade_date=2026-10-21/constituents-") for key in storage.objects)
    assert any(key.startswith("raw/source=yahoo_search/trade_date=2026-10-21/lookups-") for key in storage.objects)
    assert "universe/trade_date=2026-10-21/candidates.json" in storage.objects
    assert "universe/trade_date=2026-10-21/universe.json" in storage.objects
    assert any(key.startswith("raw/source=yahoo/trade_date=2026-10-21/chart-") for key in storage.objects)
    assert "reference/yahoo-symbols.json" in storage.objects
    assert "reference/yahoo-bar-watermarks.json" in storage.objects
    assert client.close.call_count == 3
    assert storage.closed
