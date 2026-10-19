import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from sentinel.api.config import ApiSettings
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.liveness import AgentLiveness
from sentinel.core.observability.logging import configure_logging
from sentinel.core.observability.metrics import StateCollector, serve
from sentinel.core.persistence.postgres import PostgresDatabase
from sentinel.core.persistence.queries import IncidentReader, PrReviewReader

logger = logging.getLogger(__name__)


@asynccontextmanager
async def application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = ApiSettings()
    configure_logging(settings.logging.level)
    database = PostgresDatabase(settings.database_dsn)
    try:
        sre = AgentDomain.SRE in settings.agents
        reviews = AgentDomain.PULL_REQUEST_REVIEW in settings.agents
        incidents = IncidentReader(database) if sre else None
        pull_requests = PrReviewReader(database) if reviews else None
        collector = StateCollector(incidents, pull_requests)
        serve(collector)
        application.state.settings = settings
        application.state.database = database
        application.state.liveness = AgentLiveness(settings)
        release = version("sentinel-core")
        agent_count = len(settings.agents)
        logger.info("Sentinel API ready version=%s agents=%s", release, agent_count)
        yield
    finally:
        database.close()
