# Sentinel messaging, delivery, and audit

Alertmanager's webhook receiver posts notifications to the API (`POST /api/events/alertmanager`), which publishes
each alert in them to `sentinel.cluster.alerts` keyed by its fingerprint; they are consumed by the incident workflow
in sentinel-workflow.
API actions and scheduled PR discovery publish `WorkflowRequest`s, each naming its `domain`, to
`sentinel.workflow.requests`; one workflow consumer routes each request to that domain's workflow. The
workflow claims and prepares each request using the incident or review state machine,
then sends the prepared command to its agent topic, or a side effect to `sentinel.executor.commands`.
Agents publish returns to `sentinel.sre.returns` or `sentinel.pr-review.returns`; sentinel-executor publishes every
`ExecutorReturn` to `sentinel.executor.returns`, routed by its `domain`. The workflow applies returns and publishes
committed domain snapshots to `sentinel.workflow.outcomes`. When an event moves a record into a terminal status
(incidents: `awaiting`, `blocked`, `failed`, `resolved`; reviews: `blocked`, `failed`, `merged`), the workflow posts
it to Discord itself; a failed notification is logged and changes nothing. The webhook URL is the credential, so the
workflow redacts it from `httpx` request logs (`redact_logged_secrets` in `sentinel/core/src/sentinel/core/observability/logging.py`).
Incidents Sentinel never investigated do not notify; Spark archives every snapshot as its own
object under its workflow ID (`.../workflow_id=<id>/<partition>-<offset>.jsonl`), so a workflow keeps
its whole history and a replayed record rewrites only itself. Knowledge indexing reads only the S3 knowledge files, not these records.

Kafka offsets are committed after the handler succeeds. A crash can therefore repeat a
command or return. Domain workflow IDs fence stale returns, and the state machines
decide whether repeated transitions are accepted, unchanged, or rejected. sentinel-executor
reconciles GitHub merges and fix submissions before repeating them. A repeated manual action
return is recognized by workflow ID and claim time.

Malformed events are logged and skipped. An event whose handler fails marks the incident or review
its workflow owns as failed, then is logged and skipped; consumers do not retry, and an operator
replays the record from the UI. A periodic workflow pass fails incident and review workflows
that remain acknowledged or processing beyond their time limits. Kafka is a delivery
log; PostgreSQL holds operator-visible status and history.

Agents return bounded audit actions with their decisions. Sentinel stores those actions in
the incident or review record.

Each agent tool has its own call budget per run (`max_tool_calls` in `sre.yaml` and
`pr-review.yaml`). A call past a tool's budget is refused back to the model, which then answers with
the evidence it already gathered, so reaching the budget never fails the run. Every result carries a
`tool_budget` (the limit, calls per tool, and the tools that were refused), stored in the record's
`tool_budget` column; a run that reached its budget also records a `tool_budget_exhausted` audit
action and logs a warning with the incident or pull request. Keep credentials out of commands, results, and logs.

Sources: `sentinel/workflow/src/sentinel/workflow/runner.py`, `sentinel/executor/src/sentinel/executor/`, `sentinel/core/src/sentinel/core/kafka/`,
`sentinel/workflow/src/sentinel/workflow/incidents/`, `sentinel/workflow/src/sentinel/workflow/reviews/`, and
`sentinel/core/src/sentinel/core/persistence/postgres.py`.
