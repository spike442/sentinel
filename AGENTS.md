# Sentinel agent instructions

These rules apply to every coding agent working in this repository (Claude Code reads them through `CLAUDE.md`, Codex and others read `AGENTS.md` directly).

## Start here

- Work from the repository root. Check `git status --short` and preserve existing edits.
- Use the source map below; check the relevant `infra/context/sentinel/knowledge/` document against current code.
- Make deployment changes in Git. Homelab is a separate GitOps repository; do not edit the live cluster. Installs are always fresh: do not add backup, restore, upgrade, or migration paths.
- Do not commit, push, or publish unless asked.

## Source map

| Path | Responsibility |
| --- | --- |
| `sentinel/` | Named uv workspace, its lockfile, one shared library, seven deployable modules, and their startup tests |
| `sentinel/api/` | HTTP API under `/api`: the only entry point for external triggers (operators and Alertmanager), read-only state queries, and request publishing |
| `sentinel/ui/` | React UI, built into its own nginx image and Deployment; calls the API on the same hostname under `/api` |
| `sentinel/workflow/` | Incident and PR review state machines, write repositories, and one process and Deployment |
| `sentinel/sre/` | SRE Kafka worker and its image |
| `sentinel/pr-review/` | PR review Kafka worker and its image |
| `sentinel/executor/` | GitHub and cluster side effects (fix pull requests, merges, manual actions), plus its image |
| `sentinel/knowledge/` | Private retrieval API, indexing, ClickHouse, S3 sources, and its image |
| `sentinel/core/` | Shared contracts, records, read-only queries, Kafka and database adapters, and agent support; dependencies selected by extras |
| `infra/chart/sentinel/` | Helm chart and site configuration |
| `infra/ansible/` | Prompted workstation deployment for SQL and S3 context |
| `infra/context/<repository>/` | Repository knowledge and agent prompts published to S3 |
| `sentinel/spark/` | Spark streaming archive module, its image, and its startup test |

Each deployable module has its own project and image. State changes belong to the workflow;
the API reads records and publishes operator requests over Kafka. Decisions live in pure modules;
I/O lives at the edges.

- `sentinel/workflow/src/sentinel/workflow/incidents/` and `sentinel/workflow/src/sentinel/workflow/reviews/` share one layout. `snapshot.py` (frozen record
  snapshot), `events.py`, and `machine.py` form the pure state machine: every change is a
  function `(snapshot, event, now) -> Outcome` listed in `TRANSITIONS`. Status sets are
  pure rules in `sentinel/core/src/sentinel/core/state/incident_rules.py` and `review_rules.py`, shared with the API. `repository.py` applies events through
  `postgres.apply_event` (lock, snapshot, transition, write) and persists rows defined in core.
  `sentinel/api/src/sentinel/api/requests.py` publishes operator requests. Each domain's `workflow.py` is a
  `DomainWorkflow` (`sentinel/workflow/src/sentinel/workflow/routing.py`): its tables map each topic, request kind,
  and executor action to the component that owns it, and `__main__.py` builds the consumers from those tables.
  `sentinel/workflow/src/sentinel/workflow/messages.py` (`DomainMessages`) is every domain's Kafka side (agent
  commands, executor commands, scheduled requests, outcomes) and its Discord notifications;
  `sentinel/workflow/src/sentinel/workflow/__main__.py` starts both enabled workflows. The workflow owns PostgreSQL transitions and
  decide every external side effect, but perform none: they publish typed
  `ExecutorCommand`s and apply the matching `ExecutorReturn`.
- Incident components: `investigation.py` (cluster alerts, agent runs, timeouts, and skipping alerts that
  `alertmanager.py` no longer reports firing), `submission.py`
  (claim a fix and apply the executor's pull request), and `manual_actions.py` (claim, run, record,
  expire). Incidents also add the pure `fix_policy.py`; the API normalizes Alertmanager webhook alerts before
  publishing them.
- Review components: `discovery.py` (open pull requests to review), `review.py` (agent runs and
  timeouts), `merge.py` (approved merges), `replay.py` (reconcile and review again), and `fix.py` (an operator's Fix it
  of a blocked review: the reviewer's fix, the pure `fix_policy.py`, and the executor's push). A review is one record
  per pull request. Both domains keep every agent run as an attempt and every status change in a timeline, never
  trimmed, through the pure `sentinel/core/src/sentinel/core/state/history.py`. Discovery, replay, and fix
  read GitHub directly through `sentinel/core/src/sentinel/core/github.py` (`GitHubReader` with `READ_ONLY` tokens).
- `sentinel/executor/` holds `actions.py` (one idempotent handler per `ExecutorAction`; every action changes something), `github.py` (the write gateway on the core `GitHubReader`),
  `git_workspace.py`, `commands.py` (bounded manual-action runs), `settings.py`, and `worker.py`.
- `sentinel/core/src/sentinel/core/state/outcomes.py` defines pure transition outcomes and the `require_*` helpers that
  map them to `NotFound` and `Conflict` errors at the repository boundary.
- `sentinel/sre/src/sentinel/agents/sre/` and `sentinel/pr-review/src/sentinel/agents/pr_review/` share one flat layout:
  `worker.py` (Kafka command in, return out), `runtime.py` (a context manager that builds the run and owns its
  resources), `run.py` (the deterministic steps of one investigation or review: `IncidentInvestigation`,
  `ReviewRun`), `agent.py` (only the model: prompts, messages, and the structured answer: `DiagnosisAgent`,
  `ReviewAgent`, one LangChain agent per repository), `tools.py` (tool context and tools), and `settings.py`. SRE adds `commands.py` (`CommandRunner`, bounded read-only
  shell pipelines) and `prometheus.py`; PR Review, whose reviews use only `search_knowledge` and whose fixes add `read_file` on the checkout, adds the pure `policy.py` and
  `workspace.py`.
  `sentinel/core/src/sentinel/core/agents/` holds the LangChain audit middleware, the S3 prompt loader, and `langchain.py` (model client, structured agent with its per-tool limits and run-deadline middleware, reference
  material, and `search_knowledge` tool shared by both agents); `sentinel/core/src/sentinel/core/deadline.py` holds the
  run deadline every agent run and executor action stops at.
`sentinel/api/src/sentinel/api/lifespan.py` builds the API's settings, database, and metrics; workers construct only the clients they use. The process entry
points are `sentinel.api.server`, `sentinel.workflow`, `sentinel.executor.worker`, `sentinel.agents.sre.worker`,
`sentinel.agents.pr_review.worker`, `sentinel.knowledge.api.main`, and `sentinel.spark.main`.

### Working in this repository

Run `task setup` from the repository root. The Python workspace is `sentinel/`; run `uv` package
commands there. The React app is `sentinel/ui/`. Run the seven startup tests with
`cd sentinel && .venv/bin/python -m pytest -q`, then check Python with
`sentinel/.venv/bin/ruff check sentinel` and `sentinel/.venv/bin/ruff format --check sentinel`.
CI builds every module's image from `.github/workflows/sentinel.yml` on every run, and Publish pushes all of them; the core
library is installed only as a dependency. Publish (`.github/workflows/publish.yml`) builds, checks, and publishes the
current version's images and chart, tags that commit `sentinel-<version>` (moving the tag when a version is
republished), and sends a `sentinel-release` repository dispatch to Homelab, whose Renovate commits a new chart
version to Homelab `main`. Publish never changes versions: to release a new one, set the same version in the root
project, every workspace member, `uv.lock` (`uv lock`), and the chart's `version` and `appVersion`, then run Publish. Workstation CLI tools come from dotfiles, while
CI installs its pinned Helm version with `azure/setup-helm`.
Read `infra/context/sentinel/knowledge/` for behavior and deployment boundaries before changing
a component. Deployment changes belong in Git; Homelab owns external databases, Kafka,
secrets, and site values.

## Code style

- Write no comments in any language (Python, TypeScript, YAML, SQL, Helm templates, Ansible). Name things so the code explains itself and put explanations in `infra/context/sentinel/knowledge/` or the source map in this file. Write no one-line Python docstrings; multi-line docstrings stay. The exceptions are docstrings the runtime reads: a LangChain `@tool` function's docstring is its description for the model, and a Pydantic model's class docstring is its JSON schema description in structured answers (`ProposedChange`, `PrFix`). Keep only functional comments: shebangs, `# yaml-language-server:` schema hints, `# renovate:` markers, `# vX` pins after action SHAs, Dockerfile `syntax=`, lint directives (`# noqa`, `# type: ignore`), and `/// <reference>`.

## Architecture

- `sentinel/pyproject.toml` and `sentinel/uv.lock` define the uv workspace. Its eight members are `sentinel/core/`, `sentinel/api/`, `sentinel/workflow/`, `sentinel/sre/`, `sentinel/pr-review/`, `sentinel/executor/`, `sentinel/knowledge/`, and `sentinel/spark/`. Core is a shared library; the other seven members each own a Dockerfile and startup test. Spark code lives in `sentinel/spark/src/sentinel/spark/`; PySpark comes from its pinned base image.
- `sentinel/core/src/sentinel/core/` is one shared namespace. `domain.py`, `contracts/`, and `state/outcomes.py` contain pure shared types; runtime adapters such as `config/`, `kafka/`, and `postgres.py` may depend on them, but pure modules do not import runtime adapters.
- `sentinel/api/src/sentinel/api/` serves every route under `/api`, reads records, and publishes operator requests and Alertmanager events; every external trigger enters through it. `sentinel/ui/` is a static React app served by its own Deployment; the HTTPRoute sends `/api` to the API and everything else to the UI. `sentinel/workflow/src/sentinel/workflow/incidents/` and `sentinel/workflow/src/sentinel/workflow/reviews/` own workflow execution, write repositories, and state machines. `sentinel/sre/src/sentinel/agents/` and `sentinel/pr-review/src/sentinel/agents/` contain isolated Kafka consumers; Workflow decides external side effects; `sentinel/executor/src/sentinel/executor/` alone performs them.
- Keep packages flat and dependencies direct: workflow → repository → pure state machine. Put status transitions in each domain's `machine.py`, not in repository code. Do not nest calls in logic: assign each call's result to a named variable before passing it to another call, returning it, or testing it (write `queued = with_event(...)` then `return Accepted(queued)`, not `return Accepted(with_event(...))`). Declarative constructs are exempt: SQLAlchemy column types and query builders (`mapped_column(DateTime(...))`, `select(func.count())`) and `SettingsConfigDict(yaml_file=config_files(...))`. Apply them through `postgres.apply_event`. The workflow graphs in `sentinel.core.state.workflows` are the enforced contract: each machine's `transition` rejects a status change the graph does not list, so a new status change needs its edge there. Use the pure rules in `sentinel.core.state` (`incident_rules.py`, `review_rules.py`) and policy functions for decisions, with I/O at the edges. Keep LangChain imports inside `sentinel/core/src/sentinel/core/agents/`, `sentinel/sre/src/sentinel/agents/`, and `sentinel/pr-review/src/sentinel/agents/`.
- Use `sentinel.core.errors.NotFound` and `Conflict` for expected API errors. The API maps `SentinelError` to 404/409; unexpected built-in exceptions remain 500s.
- Kafka requests, agent and executor commands, results, and final outcomes use Pydantic contracts in `sentinel/core/src/sentinel/core/kafka/contracts.py`; executor payloads live in `sentinel/core/src/sentinel/core/contracts/executor.py`. Credentials use `SecretStr` and are unwrapped only at client boundaries.
- `sentinel/knowledge/src/sentinel/knowledge/` owns retrieval and indexing. One knowledge process serves search and runs periodic indexing with the pinned model from the `sentinel-knowledge` image; embeddings are always local. `sentinel/knowledge/Dockerfile` pins the model with `ARG EMBEDDING_REVISION` and fetches each file with `ADD --checksum`, exporting the revision as `SENTINEL_RAG__EMBEDDING_REVISION`; `knowledge.yaml` names only the fastembed model and its local path.
- `sentinel/workflow/src/sentinel/workflow/runner.py` runs both enabled state machines in one Workflow process; the workflow reads what it decides on directly (GitHub pull requests with read-only installation tokens of the GitHub App, Alertmanager's alerts, knowledge search) and posts Discord notifications, but changes nothing else: every change to GitHub or the cluster is an `ExecutorCommand` that sentinel-executor alone performs, and the API holds no GitHub credentials; `sentinel/spark/` holds the streaming archive job; `sentinel/ui/` is React. `infra/chart/sentinel/` is the chart; its `config/` holds the Homelab site configuration that Sentinel runs with.
- Workstation CLI tools are managed by dotfiles. CI installs pinned Helm with `azure/setup-helm`; component images install only their own runtime dependencies and required tools.

## Data and deployment conventions

- PostgreSQL stores current incident and review fields in columns and structured histories in JSONB. Delete removes the row. Apply `infra/sql/` to fresh databases with `task deploy`, which runs the highest version folder from scratch; there are no application migrations or upgrade scripts. While a release is in development, change its folder (currently `1.0.0`) in place.
- `task deploy` uses `gum` to select one component of `infra/ansible/deploy.yaml`; `task deploy COMPONENT=<clickhouse|postgresql|s3>` selects it explicitly. The workstation reaches every service directly (no port forwards). Inventory hosts are services; `host_vars/<host>/main.yaml` holds its known settings and `secrets.yaml` only 1Password lookups; there are no role defaults. `roles/sql` deploys `infra/sql/<highest version>/<host>/` with `roles/sql/tasks/<host>.yaml`, one task per datastore running its native client (`psql`, `clickhouse client`) in one session; a new datastore is a new `sql` host, its task file, and its SQL folder. ClickHouse authenticates the client as `admin`; its runtime-user password is rendered only into a temporary bootstrap file and never committed. The playbook must pass `ansible-lint --profile production`.
- The chart owns Sentinel resources in its release namespace and Sentinel's Strimzi `KafkaTopic`s in the Kafka namespace (`kafka.topicNamespace`), rendered from the same `kafka.topics` map the processes read and kept on uninstall. Homelab owns database roles, Kafka users and their ACLs, secrets, and site values. One-time initialization (ClickHouse database and user, both schemas, prompts and knowledge) runs by hand through `task deploy COMPONENT=<clickhouse|postgresql|s3>` (`infra/ansible/deploy.yaml`); add new initialization components to the Taskfile and playbook, not to scripts or Jobs. Do not embed credentials here.
- Reconcile GitHub side effects on replay. Preserve manual-action claims; submissions, merges, and fix pushes hold no claim, and the executor's GitHub reconciliation keeps a replay from repeating a PR, merge, or fix commit. Agents self-manage: the hard boundary is that agents never read secrets (no Secrets RBAC, blocked credential paths and program execution in agent commands, redacted output, credential-free fixes); do not add other approval gates. PR auto-merge requires passing checks and the configured risk and confidence levels; there are no path, kind, author, or deletion gates, so PR Review merges SRE fix PRs like any other. Incident fixes may change any repository-relative path and kind and must contain no credential material. Nothing retries automatically: a failed incident or review stays failed until an operator replays it from the UI (replay and retry are one operation, called Replay). A blocked review is fixed only when an operator chooses Fix it; the fix is pushed to the PR only if the fixed revision passes the checks and contains no credential material. Manual actions are operations the agents cannot perform (for example job cleanup) and are the one step that waits for operator approval in the UI; sentinel-executor runs approved single commands without a shell, under its narrow `sentinel-executor` ClusterRole.
- The API has no authentication; it is reachable only through the internal gateway. Kafka consumers do not retry: a message whose handling fails marks the incident or review its workflow owns as failed (`DomainWorkflow.fail_record`), then is logged and skipped. Operators replay only from the UI; nothing re-runs work on its own. Entering a terminal status (incidents: `awaiting`, `blocked`, `failed`, `resolved`; reviews: `blocked`, `failed`, `merged`) makes the workflow post it to Discord with `DISCORD_WEBHOOK_URL` (`sentinel/workflow/src/sentinel/workflow/discord.py`, which redacts the webhook URL from `httpx` logs); a notification that cannot be sent never changes the record.

## Validate changes

- Install dependencies with `task setup` (or `cd sentinel && uv sync --locked --all-packages --group dev`, then `npm --prefix sentinel/ui ci` and `pre-commit install`). `pre-commit`, `gitleaks`, and `ruff` come from the dotfiles aqua config; the hooks in `.pre-commit-config.yaml` scan staged changes for secrets with gitleaks and run ruff lint and format. Run `task lint` (`pre-commit run --all-files`) before reporting completion; keep the dev-group ruff pin equal to the aqua version.
- Python: `sentinel/.venv/bin/ruff check sentinel`, `sentinel/.venv/bin/ruff format --check sentinel`, and `cd sentinel && .venv/bin/python -m pytest -q`.
- Tests: exactly one startup test beside each deployable Python module (`sentinel/<module>/tests/test_<module>_starts.py`, including Spark). Each test runs its module's real entry point with only external clients (PostgreSQL, Kafka, GitHub, S3, the LLM, Spark) replaced, and checks that the module reaches serving or consuming. The tests read the configuration the Deployments mount: in CI the shared `setup-sentinel` action renders the chart's config ConfigMaps with its pinned Helm and points `SENTINEL_CONFIG_DIR` at them. Do not add behavior tests to the repository; validate behavior changes with throwaway tests outside it. The UI has no startup test; its check is the build.
- UI: `npm --prefix sentinel/ui run build`.
- Chart when touched: `helm lint --strict infra/chart/sentinel` and `helm template sentinel infra/chart/sentinel --namespace agents`; render with `--set spark.enabled=true --set spark.storageClass=openebs-hostpath` when changing Spark templates.
- Remove temporary build output after local wheel or UI builds; keep the workspace clean.
- Run `git diff --check` and review changed files before reporting completion.
