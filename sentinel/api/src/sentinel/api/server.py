from importlib.metadata import version

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sentinel.api.lifespan import application_lifespan
from sentinel.api.routes.agents import router as agents_router
from sentinel.api.routes.pr_review import router as pr_review_router
from sentinel.api.routes.sre import router as sre_router
from sentinel.core.errors import Conflict, NotFound, SentinelError
from sqlalchemy import text

ERROR_STATUS = {NotFound: 404, Conflict: 409}
API_PREFIX = "/api"


async def domain_error(_request: Request, error: Exception) -> JSONResponse:
    status = next((code for kind, code in ERROR_STATUS.items() if isinstance(error, kind)), 400)
    return JSONResponse(status_code=status, content={"detail": str(error)})


def create_app() -> FastAPI:
    release = version("sentinel-core")
    application = FastAPI(title="Sentinel", version=release, lifespan=application_lifespan)
    application.add_exception_handler(SentinelError, domain_error)

    @application.get(f"{API_PREFIX}/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": release}

    @application.get(f"{API_PREFIX}/readyz")
    def readyz() -> dict[str, str]:
        probe = text("SELECT 1")
        with application.state.database.engine.connect() as connection:
            connection.execute(probe)
        return {"status": "ready"}

    application.include_router(agents_router, prefix=API_PREFIX)
    application.include_router(sre_router, prefix=API_PREFIX)
    application.include_router(pr_review_router, prefix=API_PREFIX)
    return application


app = create_app()
