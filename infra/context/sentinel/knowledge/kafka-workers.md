# Kafka workflow workers

Sentinel owns incident and review state in PostgreSQL. Alertmanager's webhook receiver posts each notification to
the API at `POST /api/sre/events/alertmanager`, which normalizes every alert in it to an `Alert` (adding `source:
alertmanager` unless the alert already has a source) and publishes it to `sentinel.cluster.alerts` keyed by its
fingerprint, so one alert's firing and resolution stay ordered. The API replies only after the broker acknowledges
each alert (a non-2xx reply makes Alertmanager retry). Repeated notifications for an alert that is already queued or
running leave the incident unchanged. The incident workflow in sentinel-workflow consumes those alerts directly.
The API publishes alerts even while SRE is disabled: `sentinel.cluster.alerts` keeps them for the topic retention
(`kafka.topicRetentionMs`, seven days), and when SRE is enabled again the incident workflow consumes the backlog
from its committed offset in order. An alert that fired and resolved meanwhile is no longer active in
Alertmanager, so the workflow marks it `skipped` instead of dispatching it, and its resolved event then resolves it. API requests
and scheduled discovery share `sentinel.workflow.requests`: each `WorkflowRequest` names its `domain`
(incidents and manual actions for `sre`; discovery, reviews, replays, and fixes for `pr-review`), and one
workflow consumer routes it to that domain's workflow, discarding a disabled domain. The workflow uses
the pure state machines to claim and prepare work, then publishes a typed command to
`sentinel.sre.commands`, `sentinel.pr-review.commands`, or `sentinel.executor.commands`.

Both SRE agents run in one process (`sentinel.sre.worker`, one container of the `sentinel-sre` Deployment),
each on its own thread and consumer group (`sentinel-incident`, `sentinel-review`); if either loop stops, the
process exits and Kubernetes restarts it. They receive prepared requests with RAG context and publish to `sentinel.sre.returns` or
`sentinel.pr-review.returns` before committing their command offsets. Every message about a record carries
the record's ID (`record_id`, the incident or review) beside its workflow ID: workflow requests (all but discovery),
agent commands and returns, and executor commands and returns. Returns contain both IDs, a small original request,
and either the agent's result or a `RunFailure` (the error type, and for a run that started, its audit actions
and tool budget, which the failed attempt keeps).
The `KafkaTopic` keys in code are internal routing names; broker topic names come from the
chart's `kafka.topics` values, which also create the topics, rendered into each process's configuration. Shared Kafka connection
settings live in `common/kafka.yaml`.
Each worker loads its model, prompt store, and clients once at startup and closes them when its
consumer exits. Both agents read each prompt from S3 once per process; a changed prompt takes
effect when the worker restarts.

`sentinel-executor` consumes `sentinel.executor.commands`. Each `ExecutorCommand` names an
`ExecutorAction` (`create-pull-request`, `merge-pull-request`, `run-command`): every action changes
GitHub or the cluster; the workflow does its own reads and posts Discord notifications itself. Each command carries its typed payload, its record and workflow IDs, and
optional workflow `context` (only a manual action's claim) that come back unchanged. The executor publishes the `ExecutorReturn` to `sentinel.executor.returns` before committing
the command; Workflow routes it by the return's `domain`. Workflow applies every
return through the domain workflow and repository; the pure machine decides transitions.

An incident fix is saved, the incident still `running` (diagnosis and audit actions included), before the
executor opens its pull request; the command names the incident only by its record ID, so it stays within Kafka's
message size limit. An approved review stays `running` while the executor merges exactly the reviewed head
SHA; a merge GitHub confirms is recorded whichever workflow owns the review by then. Neither holds a lease:
an operator may replay a running incident or review from the UI at any time, and the executor's GitHub
reconciliation keeps that from repeating a pull request or merge. A manual action runs within its own timeout.
Discovery reads open pull requests and their mergeability from GitHub, then schedules each one whose current
revision needs review. A review replay reads the pull request: a merged one is recorded, a closed one is
rejected with the reason on the review, and an open one is reviewed again at its current revision. A fix
sends the PR Review worker a `fix` command; the executor's `push-fix` has GitHub create a signed commit of the accepted
fix on exactly the reviewed head and fast-forwards the branch to it without force, finds its own commit when a command is repeated, and fails when
the branch moved.

Kafka delivery repeats only when a process dies mid-message. Workflow IDs fence stale returns; manual
action records are idempotent by workflow ID and claim time. The executor reconciles GitHub before
repeating an effect: it reuses an existing pull request or branch and checks for an existing merge
first. A repeated fix result or merge claim for the same workflow changes nothing. Manual actions run
at most once: sentinel-executor commits the command's offset before it runs, so an executor crash
never reruns one; the action's timeout then marks it failed. A repeated alert does not restart an
incident that already has a workflow.

Each role has its own Kafka user. `sentinel` (API and workflow) uses the `sentinel.` topics; `sentinel-sre`
(both SRE agents) reads only the SRE and PR review commands and writes only their returns, and `sentinel-executor` reads
`sentinel.executor.commands` and writes only `sentinel.executor.returns`, so an agent cannot publish executor
commands or returns. Topics are split by producer: each agent keeps its own command and return topic,
so no agent can write another agent's results, while topics with one producer and one consumer for
every domain (`sentinel.workflow.requests`, `sentinel.executor.returns`) are shared and carry the `domain`.
Adding a domain agent adds only its command and return topics. Agents and sentinel-executor touch `/tmp/sentinel-worker-heartbeat` on every poll.

Every time limit is one chart value: `agents.<agent>.runTimeoutSeconds` (1800) for an agent run and
`executor.actionTimeoutSeconds` (900) for an executor action. An agent's deadline is its run timeout counted from
when the workflow published the command, and anything not finished by then is timed out: a command that waited in
the queue past it fails at once, the deadline is checked before every model and tool call and bounds every git
command, and a result the model produced after it is reported as `RunTimedOut`. The workflow fails a run still
running after the same run timeout, liveness probes and termination grace use the same timeouts, and Kafka's
`max_poll_interval_seconds` is twice the longest of them. The workflow expires stalled incident and review workflows through their failure transitions, and marks stale
running manual actions as timed out.
A message whose handling fails marks its incident or review failed and is skipped; consumers do not
retry, and PR discovery does not review a failed revision again. Operators replay from the UI. Inspect consumer lag,
worker logs, and persisted state when work stops progressing.

The knowledge service indexes on startup and every `rag.index_interval_seconds`. PR discovery is
scheduled by the review workflow in sentinel-workflow and can also be requested from the API.

Sources: `sentinel/workflow/src/sentinel/workflow/`, `sentinel/executor/src/sentinel/executor/`,
`sentinel/core/src/sentinel/core/kafka/`,
`sentinel/workflow/src/sentinel/workflow/sre/incidents/`, `sentinel/workflow/src/sentinel/workflow/sre/reviews/`,
`sentinel/sre/src/sentinel/sre/incidents/worker.py`, `sentinel/sre/src/sentinel/sre/reviews/worker.py`, and
`infra/chart/sentinel/templates/`.
