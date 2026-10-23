# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.20@sha256:100047e74f30778ab704942321a09750d6158739573ff58bf3924085cc6cd2d8 AS uv
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS cli-tools

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tar \
    && curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
      -o /tmp/kubectl https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl \
    && echo "65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8  /tmp/kubectl" | sha256sum -c - \
    && curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
      -o /tmp/flux.tar.gz https://github.com/fluxcd/flux2/releases/download/v2.9.6/flux_2.9.6_linux_amd64.tar.gz \
    && echo "b4d22673e9246cbd628881f1a9ef3b090085dced291e42d804555cee8e8d42c5  /tmp/flux.tar.gz" | sha256sum -c - \
    && curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
      -o /tmp/helm.tar.gz https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz \
    && echo "0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b  /tmp/helm.tar.gz" | sha256sum -c - \
    && curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
      -o /tmp/yq https://github.com/mikefarah/yq/releases/download/v4.54.1/yq_linux_amd64 \
    && echo "8e34fc298390875de416e6a4afcb8cabeceb25d9aa8506c1a2f9353cf702ea5f  /tmp/yq" | sha256sum -c - \
    && install -m 0755 /tmp/kubectl /usr/local/bin/kubectl \
    && install -m 0755 /tmp/yq /usr/local/bin/yq \
    && tar -xzf /tmp/flux.tar.gz -C /usr/local/bin flux \
    && tar -xzf /tmp/helm.tar.gz -C /usr/local/bin --strip-components=1 linux-amd64/helm
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=0
COPY sentinel/pyproject.toml sentinel/uv.lock ./
COPY sentinel/core ./core
COPY sentinel/agents ./agents
COPY sentinel/sre ./sre
RUN --mount=from=uv,source=/uv,target=/bin/uv UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --no-dev --package sentinel-sre --no-editable
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates passwd git jq ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 65532 --create-home --shell /usr/sbin/nologin sentinel
COPY --from=build /app/.venv /app/.venv
COPY --from=cli-tools /usr/local/bin/kubectl /usr/local/bin/kubectl
COPY --from=cli-tools /usr/local/bin/flux /usr/local/bin/flux
COPY --from=cli-tools /usr/local/bin/helm /usr/local/bin/helm
COPY --from=cli-tools /usr/local/bin/yq /usr/local/bin/yq
ENV GIT_TERMINAL_PROMPT=0
USER 65532:65532
CMD ["python", "-m", "sentinel.sre.worker"]
