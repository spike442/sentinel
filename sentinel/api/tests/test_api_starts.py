import asyncio
from unittest.mock import Mock


def test_api_starts_and_reports_healthy(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DATABASE_PASSWORD", "test")
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")
    database = Mock()
    monkeypatch.setattr("sentinel.api.lifespan.PostgresDatabase", Mock(return_value=database))
    monkeypatch.setattr("sentinel.api.lifespan.serve", Mock())
    monkeypatch.setattr("sentinel.api.lifespan.AgentLiveness", Mock())
    from sentinel.api.server import create_app

    app = create_app()

    async def verify() -> dict[str, str]:
        async with app.router.lifespan_context(app):
            route = next(route for route in app.routes if route.path == "/api/healthz")
            return route.endpoint()

    response = asyncio.run(verify())
    assert response["status"] == "ok"
