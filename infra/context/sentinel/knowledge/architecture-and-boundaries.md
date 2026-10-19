# Sentinel architecture and module boundaries

Repository: `sentinel`. Scope: agent platform responsibilities and package structure.

`sentinel/` is the uv workspace parent. Eight Python modules live under it:
core, API, workflow, SRE, PR review, executor, knowledge, and Spark. The API serves HTTP under `/api` and is the only entry point for external triggers; the React UI in
`sentinel/ui/` is a separate static Deployment.
One `sentinel-workflow` Deployment always runs and loads the enabled incident and review state machines: it consumes Kafka requests,
agent returns, and executor returns, owns PostgreSQL state, and publishes agent and executor
commands. Workflow decides every external side effect but performs none. It reads what it decides
on directly: GitHub pull requests for discovery, replays, and fixes, with installation tokens of the shared
GitHub App narrowed to read-only permissions (`READ_ONLY` in `sentinel/core/src/sentinel/core/github.py`),
Alertmanager's alerts, and knowledge search. `sentinel-executor` is the only process that changes
GitHub or the cluster: it pushes incident fix branches, opens and merges pull requests, and runs
approved manual actions. The workflow posts Discord notifications itself. The GitHub reads it makes only reconcile its own
actions (an existing fix PR, a PR's state before merging). SRE and PR Review run as
separate Kafka workers with distinct Kubernetes identities. Their decisions return through
Kafka; they do not write the application database or expose HTTP APIs.

Domain state lives in `sentinel/workflow/src/sentinel/workflow/incidents/` and
`sentinel/workflow/src/sentinel/workflow/reviews/`. Each domain has a
frozen snapshot, events, a pure transition table in `machine.py`, a repository that
applies transitions under a row lock, and a workflow that routes messages. Both domains have
one process entry point in `sentinel/workflow/`. Pure rules and policies do not access clients.
The API reads records and publishes operator requests. It never applies state transitions.
Shared Kafka delivery code lives in `sentinel/core/src/sentinel/core/kafka/`; the workflow's consumer runner is
`sentinel/workflow/src/sentinel/workflow/runner.py`; the executor is `sentinel/executor/`.
The shared package has one `sentinel.core` namespace. `domain`, `contracts`, and `state` hold
shared types and pure decisions. `persistence` holds PostgreSQL records and readers;
`observability` holds audit trails, logging, and metrics; `commands` holds command validation
and execution. `agents` holds shared prompt loading and LangChain audit middleware.
`config`, `kafka`, and the remaining runtime modules hold external clients.
Runtime modules may import pure modules;
pure modules do not import runtime modules. Repositories map missing or rejected outcomes to
API errors through the `require_*` helpers in `sentinel.core.state.outcomes`.
`sentinel.core.domain` holds shared statuses, levels, and `RepositoryIdentity`.
`sentinel.core.contracts` holds the request and result shapes exchanged by processes, including
`PullRequest`, `KnowledgeSearchRequest`, and `RetrievedContext`.

`sentinel/sre/` and `sentinel/pr-review/` own LLM execution and tools. `sentinel/knowledge/` owns
the private knowledge service: retrieval API, embeddings, ClickHouse access, and the
periodic indexing loop it runs. `sentinel/spark/` archives final workflow outcomes. The UI talks to Sentinel only.

The API can accept requests while workers restart because Kafka retains accepted
commands. A worker publishes a return before committing its command offset. Sentinel's
state machine fences stale or repeated returns. PostgreSQL remains the source of truth
for incident and review status, history, and audit actions.

Sources: `sentinel/api/src/sentinel/api/`, `sentinel/core/src/sentinel/core/`, `sentinel/executor/src/sentinel/executor/`, `sentinel/sre/src/sentinel/agents/` and `sentinel/pr-review/src/sentinel/agents/`,
`sentinel/workflow/src/sentinel/workflow/`, `sentinel/knowledge/src/sentinel/knowledge/`,
`sentinel/spark/`, and `infra/chart/sentinel/`.
