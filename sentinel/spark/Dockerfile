# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 AS uv
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
WORKDIR /app
COPY sentinel/pyproject.toml sentinel/uv.lock ./
COPY sentinel/spark/pyproject.toml ./spark/pyproject.toml
COPY sentinel/spark/src ./spark/src
RUN --mount=from=uv,source=/uv,target=/bin/uv UV_CACHE_DIR=/tmp/uv-cache uv export --frozen --no-dev --package sentinel-spark --no-emit-workspace --format requirements-txt -o /tmp/spark-requirements.txt \
    && UV_CACHE_DIR=/tmp/uv-cache uv build --package sentinel-spark --wheel --out-dir /tmp/wheels

FROM apache/spark:4.2.0-python3@sha256:fc64959c04bd87b0ac686be9aaa9008b69cdb1afc695400528279c8b01f43d89
USER root
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
ARG MAVEN_URL=https://repo1.maven.org/maven2
ADD --chmod=644 --checksum=sha256:64539c45e5d39f7ddb747312c239f38f5208d08c1a0ddf7d70beb2fbd9373705 ${MAVEN_URL}/org/apache/spark/spark-sql-kafka-0-10_2.13/4.2.0/spark-sql-kafka-0-10_2.13-4.2.0.jar /opt/spark/jars/
ADD --chmod=644 --checksum=sha256:641c7947afc8aa1189e433b7c2d305293993c8691bc1c2062d6d4f513b12518c ${MAVEN_URL}/org/apache/spark/spark-token-provider-kafka-0-10_2.13/4.2.0/spark-token-provider-kafka-0-10_2.13-4.2.0.jar /opt/spark/jars/
ADD --chmod=644 --checksum=sha256:014b4ef36884478a932641818b080c36a8f8e2e92dc771e800c9d2694f4f83d8 ${MAVEN_URL}/org/apache/kafka/kafka-clients/3.9.2/kafka-clients-3.9.2.jar /opt/spark/jars/
ADD --chmod=644 --checksum=sha256:f77a5060d6936a9144023584232f9de3f2248f1abfe156e9d31795f18770674f ${MAVEN_URL}/org/apache/commons/commons-pool2/2.13.1/commons-pool2-2.13.1.jar /opt/spark/jars/
COPY --from=build /tmp/spark-requirements.txt /tmp/spark-requirements.txt
COPY --from=build /tmp/wheels/sentinel_spark-*.whl /tmp/
RUN python3 -m pip install --no-cache-dir --require-hashes -r /tmp/spark-requirements.txt \
    && python3 -m pip install --no-cache-dir --no-deps /tmp/sentinel_spark-*.whl \
    && rm /tmp/spark-requirements.txt /tmp/sentinel_spark-*.whl
COPY sentinel/spark/src/sentinel/spark/main.py /opt/sentinel-spark/main.py
USER spark
