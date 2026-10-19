# Sentinel configuration, releases, and operational diagnosis

Repository: `sentinel`. Scope: startup prerequisites and safe delivery.

## Configuration and credentials

Each process keeps non-secret YAML under `infra/chart/sentinel/config/`, loaded with pydantic-settings from
`SENTINEL_CONFIG_DIR` (default `/etc/sentinel`, where the chart mounts it). Those files hold no site values:
Kafka bootstrap servers, consumer group, and topic names, S3, database and ClickHouse hosts and names, the
Prometheus URL, and the enabled agents come only from chart values, which `templates/_config.tpl` overlays. External
Secrets inject environment credentials. The API and workflow hold database and Kafka
credentials only. sentinel-executor alone holds the GitHub App credentials, for pushes, pull
requests, merges, and discovery; `workflow.yaml` supplies shared knowledge settings and
separates incident and review settings under `sre` and `pr_review`.
`common/llm.yaml` supplies the shared agent endpoint and model; agent files supply
their own LLM settings.
The current default is the OpenAI API (`https://api.openai.com/v1`) with the model named in `common/llm.yaml`,
called through LangChain's OpenAI client and the Responses API. `LLM_API_KEY` holds the OpenAI API key; it is
delivered by the Homelab secret and never committed here. `request_timeout_seconds` bounds each model request and
`max_retries` its retries.
Homelab supplies PostgreSQL and ClickHouse database and role names through `postgres` and
`clickhouse` chart values. It supplies Kafka users and the consumer group through `kafka` values. The chart's `kafka.topics`
map defines each topic's name and partitions once: the chart renders it into each process's
configuration and into Strimzi `KafkaTopic`s in `kafka.topicNamespace` (with `kafka.topicReplicas`
and `kafka.topicRetentionMs`), annotated to survive an uninstall.
Fix commits are created through the GitHub API with GitHub App installation tokens, so GitHub signs them
as the App and there is no SSH deploy or signing key. The platform shares one S3
credential, `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` from the `sentinel` item, for knowledge,
Spark, SRE and PR Review prompts, and `task deploy`. The knowledge service owns read-only
PostgreSQL and ClickHouse credentials for indexing and retrieval. SRE and PR Review own their
model and Kafka credentials.
All Sentinel credentials live in the single 1Password item `sentinel`, and each `sentinel-secrets` key matches its
field name. Exact field names belong
in current settings classes and ExternalSecrets, not in long-lived examples.

S3 context is grouped by repository under `context/<repository>/`. Mandatory agent prompts
live in `prompts/<agent>/` and retrieved documents live in `sentinel/knowledge/`. Missing prompt
credentials or objects fail startup or the relevant action. Both agents load each prompt once per
process through `PromptStore`; restart a worker to pick up an uploaded prompt change.
Knowledge indexing has a separate lifecycle from prompt refresh.

HOME, KUBECONFIG, and mounted service-account material belong in the container/deployment
environment. Only SRE, PR Review, and sentinel-executor pods mount a service-account token; the API
and workflow pods do not. The agents' kubeconfigs grant only their read-only RBAC;
sentinel-executor's grants only the manual-action operations of its `sentinel-executor` ClusterRole. Workers use internal cluster Services, not public ingress.

## Build and release

CI and Publish call one reusable workflow, `sentinel.yml`; Publish sets `publish: true`. Every run
checks Python (format, lint, startup tests), the UI build, and each chart values file in
`infra/chart/sentinel/ci/`, then builds all eight images (api, ui, workflow, sre, pr-review, executor,
knowledge, spark); CI only builds them, so every release is built from the same full set. Publish pushes and
signs every image, publishes the chart at the release version, then tags the released commit
`sentinel-<version>`, moving the tag when the same version is republished. After tagging, Publish bumps the
project, every workspace member, `uv.lock`, and the chart to the next selected version, commits that preparation
to the released branch, and notifies Homelab Renovate. The release starts from the current version in every
project, `uv.lock`, and the chart. The `setup-sentinel` composite action installs uv, Python, and the locked workspace.
Quality is reporting only and never blocks CI or Publish: it runs the Python and UI checks behind the
badge and, outside pull requests, scans every image with Trivy (HIGH and CRITICAL with a fix) and
uploads the results to GitHub code scanning under the `image-<module>` categories. The Python version
comes from `sentinel/pyproject.toml`; publication creates one Sentinel Git tag and versioned images.
An existing release tag is not silently moved to a different commit.

Each deployable module has its own image. Every workload pulls its image on each start
(`imagePullPolicy: Always`), so a node never keeps running an older image cached under a reused tag. The UI image is nginx serving the built React app; one workflow image
runs one Deployment for both enabled workflows. Each agent and sentinel-executor image installs only its module dependencies. The knowledge image
includes the pinned local model.
The Spark module runs a separate image. Its Python dependencies come from the workspace lockfile,
while the pinned Apache Spark base image supplies PySpark. The image also bakes in the Kafka
connector jars (`spark-sql-kafka`, its token provider, `kafka-clients`, and `commons-pool2`), each
pinned by checksum, so the streaming job resolves nothing from Maven at runtime. It reads the bundled
`logging.yaml`, `kafka.yaml`, `s3.yaml`, and `spark.yml`; it does not scan
unrelated configuration files. Dotfiles own workstation CLI tools; CI installs its pinned Helm
version directly, and each Docker image installs only the CLI tools it needs. Each module's
`pyproject.toml` declares its direct runtime dependencies. CLI availability and Python
dependency installation are separate prerequisites. The root Taskfile coordinates setup,
deployment, and knowledge indexing.

## Diagnose by failure layer

Startup: check Secret delivery, YAML validation, prompt objects, model connectivity,
PostgreSQL platform state, ClickHouse schema, local embedding model,
and Kafka authentication/topic existence. Sentinel API health/version and UI configuration must be
reachable; check the workflow pod, the sentinel-executor pod, and Kafka consumption separately.

Missing work: trace monitoring or GitHub discovery, request and command topics, consumer lag,
worker logs, active state, stored decision, and notification. A blocked
diagnosis is different from a transport error. GitHub failures surface in sentinel-executor's logs
and in the result the workflow records; a refused commit or branch update (a branch
that moved, a missing contents write permission) is different from GitHub API authentication. An Alertmanager event whose handling fails marks its incident failed and is skipped without retry;
inspect the workflow logs and `sentinel_cluster_alert_events_total` before replaying them. A UI error can be backend schema/configuration failure, not missing frontend assets.

Rollout: publish the Sentinel images, change their Homelab declarations, and let Flux reconcile.
Do not apply schema resets, upload S3 files, trigger work, or mutate cluster state merely while
reviewing documentation. Never log settings objects or decrypted secret values.

Sources: `.github/workflows/`, `.github/actions/`, `Taskfile.yml`,
`sentinel/*/Dockerfile`,
`sentinel/sre/src/sentinel/agents/sre/settings.py`, `sentinel/pr-review/src/sentinel/agents/pr_review/settings.py`,
`sentinel/core/src/sentinel/core/config/`, `sentinel/api/src/sentinel/api/config.py`, and
`sentinel/core/src/sentinel/core/config/workflow.py`.
