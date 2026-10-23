# Sentinel architecture and module boundaries

Repository: `sentinel`. Scope: agent platform responsibilities and package structure.

`sentinel/` is the uv workspace parent. It holds the Sentinel modules (core, the agents library, the console API, workflow,
SRE, PR review, executor, and knowledge) and the Stonks modules, the only ones with Spark, under `sentinel/stonks/`. The console groups the
operator surface: the API in `sentinel/console/api/` serves one backend per agent domain under `/api/<domain>` and is
the only entry point for external triggers (each domain's `events/` routes), and the React UI in
`sentinel/console/ui/` is a separate static Deployment that lists its domains in `/domains.json` and calls each
domain's own backend, so a domain such as Stonks (`stonks-api` under `/api/stonks`) can bring its own.
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

SRE is one domain with two workflows, each run by its own agent: incidents in
`sentinel/workflow/src/sentinel/workflow/sre/incidents/` (SRE agent) and reviews in
`sentinel/workflow/src/sentinel/workflow/sre/reviews/` (PR Review agent). Each workflow has a
frozen snapshot, events, a pure transition table in `machine.py`, a repository that
applies transitions under a row lock, and a workflow that routes messages. Both domains have
one process entry point in `sentinel/workflow/`. Pure rules and policies do not access clients.
The API reads records and publishes operator requests. It never applies state transitions.
Shared Kafka delivery code lives in `sentinel/core/src/sentinel/core/kafka/`; the workflow's consumer runner is
`sentinel/workflow/src/sentinel/workflow/runner.py`; the executor is `sentinel/executor/`.
The shared package has one `sentinel.core` namespace. `domain`, `contracts`, and `state` hold
shared types and pure decisions. `persistence` holds PostgreSQL records and readers;
`observability` holds audit trails, logging, and metrics; `commands` holds command validation
and execution.
`config`, `kafka`, and the remaining runtime modules hold external clients.
Runtime modules may import pure modules;
pure modules do not import runtime modules. Repositories map missing or rejected outcomes to
API errors through the `require_*` helpers in `sentinel.core.state.outcomes`.
`sentinel.core.domain` holds shared statuses, levels, and `RepositoryIdentity`.
`sentinel.core.contracts` holds the request and result shapes exchanged by processes, including
`PullRequest`, `KnowledgeSearchRequest`, and `RetrievedContext`.

`sentinel/agents/` is a library, not a process: `sentinel.agents.framework` holds the one agent contract
(`AgentTask`, `AgentRun`, and the `AgentRunner` that runs every task the same way), the LangChain model client, the
structured agent with its per-tool limits and run deadline, the audit middleware, the S3 prompt loader, and the shared
knowledge tool; each agent (`sentinel.agents.sre.incident`, `sentinel.agents.sre.review`, `sentinel.agents.dividends`) declares
its tasks, tools, tool context, structured answer, and run message, and runs on the `AgentRunner` its worker builds.
Every task's system prompt is `system.md`, then `actions/<action>.md`, then `actions/<tool>.md` for each of its tools. `sentinel/sre/` (`incidents/` and `reviews/`, one process and container, `sentinel.sre.worker`) is the worker that runs those agents:
they own the Kafka loop, the checkout, the deterministic steps of a run, and policy. `sentinel/knowledge/` owns
the private knowledge service: retrieval API, embeddings, ClickHouse access, and the
periodic indexing loop it runs. The UI talks only to the domain backends `/domains.json` lists.

The API can accept requests while workers restart because Kafka retains accepted
commands. A worker publishes a return before committing its command offset. Sentinel's
state machine fences stale or repeated returns. PostgreSQL remains the source of truth
for incident and review status, history, and audit actions.

Sources: `sentinel/console/api/src/sentinel/api/`, `sentinel/core/src/sentinel/core/`, `sentinel/executor/src/sentinel/executor/`, `sentinel/agents/src/sentinel/agents/`, `sentinel/sre/src/sentinel/sre/` (`incidents/`, `reviews/`),
`sentinel/workflow/src/sentinel/workflow/`, `sentinel/knowledge/src/sentinel/knowledge/`,
and `infra/chart/sentinel/`.
