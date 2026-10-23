# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 AS uv
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
WORKDIR /app
COPY sentinel/pyproject.toml sentinel/uv.lock ./
COPY sentinel/stonks/spark/pyproject.toml ./stonks/spark/pyproject.toml
COPY sentinel/stonks/spark/src ./stonks/spark/src
RUN --mount=from=uv,source=/uv,target=/bin/uv UV_CACHE_DIR=/tmp/uv-cache uv export --frozen --no-dev --package stonks-spark --no-emit-workspace --format requirements-txt -o /tmp/spark-requirements.txt \
    && UV_CACHE_DIR=/tmp/uv-cache uv build --package stonks-spark --wheel --out-dir /tmp/wheels

FROM apache/spark:4.2.0-python3@sha256:fc64959c04bd87b0ac686be9aaa9008b69cdb1afc695400528279c8b01f43d89
USER root
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
ARG MAVEN_URL=https://repo1.maven.org/maven2
ADD --chmod=644 --checksum=sha256:66bd9eefb938b1a1657487324b63c13df2d8b17164a1dd24e0ef37b905bc5baa ${MAVEN_URL}/org/apache/hadoop/hadoop-aws/3.5.0/hadoop-aws-3.5.0.jar /opt/spark/jars/
ADD --chmod=644 --checksum=sha256:db4b55f24ad1b4e70f17eb1717a4de76a8dadc5a27d764be7c44ff67b2c1c677 ${MAVEN_URL}/software/amazon/awssdk/bundle/2.35.4/bundle-2.35.4.jar /opt/spark/jars/
COPY --from=build /tmp/spark-requirements.txt /tmp/spark-requirements.txt
COPY --from=build /tmp/wheels/stonks_spark-*.whl /tmp/
RUN python3 -m pip install --no-cache-dir --require-hashes -r /tmp/spark-requirements.txt \
    && python3 -m pip install --no-cache-dir --no-deps /tmp/stonks_spark-*.whl \
    && rm /tmp/spark-requirements.txt /tmp/stonks_spark-*.whl
COPY sentinel/stonks/spark/src/stonks/spark/main.py /opt/stonks-spark/main.py
USER spark
