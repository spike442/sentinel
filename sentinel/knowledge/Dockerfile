# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 AS uv
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=0
COPY sentinel/pyproject.toml sentinel/uv.lock ./
COPY sentinel/core ./core
COPY sentinel/knowledge ./knowledge
RUN --mount=from=uv,source=/uv,target=/bin/uv UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --no-dev --package sentinel-knowledge --no-editable
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates passwd libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 65532 --create-home --shell /usr/sbin/nologin sentinel \
    && install --directory --mode=0755 /app/models/embedding/onnx
COPY --from=build /app/.venv /app/.venv
ARG EMBEDDING_REVISION=e9b6763023c676ca8431644204f50c2b100d9aab
ARG EMBEDDING_URL=https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/resolve/${EMBEDDING_REVISION}
ADD --chmod=644 --checksum=sha256:147d5aa88c2101237358e17796cf3a227cead1ec304ec34b465bb08e9d952965 ${EMBEDDING_URL}/onnx/model.onnx /app/models/embedding/onnx/model.onnx
ADD --chmod=644 --checksum=sha256:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66 ${EMBEDDING_URL}/tokenizer.json /app/models/embedding/tokenizer.json
ADD --chmod=644 --checksum=sha256:d7e0000bcc80134debd2222220427e6bf5fa20a669f40a0d0d1409cc18e0a9bc ${EMBEDDING_URL}/tokenizer_config.json /app/models/embedding/tokenizer_config.json
ADD --chmod=644 --checksum=sha256:9ab00bd92cee80a569f708140b7b6c1661a65891ff3765b1519e181ba2f2c92b ${EMBEDDING_URL}/config.json /app/models/embedding/config.json
ADD --chmod=644 --checksum=sha256:5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a ${EMBEDDING_URL}/special_tokens_map.json /app/models/embedding/special_tokens_map.json
ENV HF_HUB_OFFLINE=1 \
    SENTINEL_RAG__EMBEDDING_REVISION=${EMBEDDING_REVISION}
USER 65532:65532
CMD ["python", "-m", "sentinel.knowledge.api.main"]
