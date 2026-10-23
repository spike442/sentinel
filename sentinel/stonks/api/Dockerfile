# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 AS uv
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=0
COPY sentinel/pyproject.toml sentinel/uv.lock ./
COPY sentinel/stonks/core ./stonks/core
COPY sentinel/stonks/api ./stonks/api
RUN --mount=from=uv,source=/uv,target=/bin/uv UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --no-dev --package stonks-api --no-editable
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates passwd \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 65532 --create-home --shell /usr/sbin/nologin stonks
COPY --from=build /app/.venv /app/.venv
EXPOSE 8090
USER 65532:65532
CMD ["uvicorn", "stonks.api.server:app", "--host", "0.0.0.0", "--port", "8090"]
