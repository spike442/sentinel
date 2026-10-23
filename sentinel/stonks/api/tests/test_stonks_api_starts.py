import io
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

CHART_CONFIG = Path(__file__).parents[4] / "infra" / "chart" / "stonks" / "config"
UNIVERSE = {
    "trade_date": "2026-10-21",
    "universe": {"instruments": [{"isin": "DE0007164600", "symbol": "SAP.DE"}], "rejections": []},
}


class MemoryS3:
    def __init__(self):
        self.objects = {"universe/trade_date=2026-10-21/universe.json": json.dumps(UNIVERSE).encode()}
        self.closed = False

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def get_paginator(self, _operation):
        paginator = MagicMock()
        contents = [{"Key": key} for key in self.objects]
        paginator.paginate.return_value = [{"Contents": contents}]
        return paginator

    def close(self):
        self.closed = True


def test_stonks_api_starts_and_serves_datasets(monkeypatch, tmp_path) -> None:
    shutil.copy(CHART_CONFIG / "common" / "logging.yaml", tmp_path)
    shutil.copy(CHART_CONFIG / "common" / "storage.yaml", tmp_path)
    (tmp_path / "s3.yaml").write_text("s3:\n  endpoint: http://s3.test\n  region: us-east-1\n  bucket: stonks\n")
    monkeypatch.setenv("STONKS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    from stonks.api.server import create_app

    from stonks.core import objects

    storage = MemoryS3()
    monkeypatch.setattr(objects.boto3, "client", MagicMock(return_value=storage))
    app = create_app()

    with TestClient(app) as client:
        ready = client.get("/api/stonks/readyz")
        universe = client.get("/api/stonks/datasets/universe")

    assert ready.json()["status"] == "ready"
    assert universe.json()["rows"] == UNIVERSE["universe"]["instruments"]
    assert storage.closed
