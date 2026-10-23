import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from importlib.metadata import version
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from stonks.api.datasets import DATASETS, columns
from stonks.api.settings import Settings
from stonks.api.store import StonksReader
from stonks.core.cli import configure_logging
from stonks.core.objects import ObjectStore, s3_client

logger = logging.getLogger(__name__)

API_PREFIX = "/api/stonks"


@asynccontextmanager
async def application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(settings.logging.level)
    client = s3_client(settings)
    try:
        objects = ObjectStore(client, settings.s3)
        application.state.reader = StonksReader(objects, settings.storage)
        release = version("stonks-api")
        logger.info("Stonks API ready version=%s", release)
        yield
    finally:
        client.close()


def reader_of(request: Request) -> StonksReader:
    return request.app.state.reader


def create_app() -> FastAPI:
    release = version("stonks-api")
    application = FastAPI(title="Stonks", version=release, lifespan=application_lifespan)
    router = APIRouter(prefix=API_PREFIX, tags=["stonks"])

    @router.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": release}

    @router.get("/readyz")
    def readyz(request: Request) -> dict[str, str]:
        reader = reader_of(request)
        reader.trade_dates()
        return {"status": "ready"}

    @router.get("/manifest")
    def manifest() -> dict[str, Any]:
        return {
            "id": "stonks",
            "label": "Stonks",
            "icon": "bull",
            "kind": "data",
            "version": release,
            "enabled": True,
            "running": True,
            "active": 0,
        }

    @router.get("/trade-dates")
    def trade_dates(request: Request) -> dict[str, list[date]]:
        reader = reader_of(request)
        available = reader.trade_dates()
        return {"trade_dates": available}

    @router.get("/datasets")
    def datasets() -> dict[str, list[dict[str, Any]]]:
        listed = [
            {"name": dataset.name, "label": dataset.label, "trade_dated": dataset.trade_dated}
            for dataset in DATASETS.values()
        ]
        return {"datasets": listed}

    @router.get("/datasets/{name}")
    def dataset(name: str, request: Request, trade_date: date | None = Query(default=None)) -> dict[str, Any]:
        found = DATASETS.get(name)
        if found is None:
            raise HTTPException(status_code=404, detail=f"unknown dataset: {name}")
        reader = reader_of(request)
        if found.trade_dated and trade_date is None:
            available = reader.trade_dates()
            if not available:
                raise HTTPException(status_code=404, detail="no trade date has a universe yet")
            trade_date = available[0]
        document = reader.document(found, trade_date if found.trade_dated else None)
        if document is None:
            raise HTTPException(status_code=404, detail=f"{found.label} is not available")
        rows = found.rows(document)
        names = columns(rows)
        return {
            "name": found.name,
            "label": found.label,
            "trade_date": trade_date if found.trade_dated else None,
            "columns": names,
            "rows": rows,
        }

    application.include_router(router)
    return application


app = create_app()
