# Sentinel SRE incident investigation and execution

Repository: `sentinel`. Scope: alert acknowledgment, diagnosis, replay, and resolution.

## Receive and investigate

Sentinel receives normalized monitoring events over Kafka. Incident identity uses the alert
fingerprint; source, labels, annotations, status, and timestamps remain alert data. Sentinel persists
firing alerts and publishes a Kafka workflow request. Incoming resolved alerts still update a matching incident,
and a stale workflow stops before investigation. Ignored incidents are an explicit
operator choice, not a successful repair.

Before dispatching an alert run, the incident workflow asks Alertmanager (`alertmanager.url`, its read-only and
credential-free alert API) whether the alert's fingerprint is still unresolved. If it is not, the queued incident
moves to `skipped` (`RunSkipped`) and no command reaches the SRE worker; this keeps a backlog of alerts that fired
and resolved while SRE was disabled, or a flapping alert, from spending investigations. Replays always dispatch,
and an Alertmanager that cannot answer counts as firing. The SRE worker only investigates what it receives: it
synchronizes the public repository and starts from the alert rather than a
whole-cluster dump. The LangChain agent uses selected native tools for bounded shell inspection,
Prometheus queries, and GitHub reads. System/action prompts specify behavior; Sentinel-supplied RAG
excerpts supply reference facts. The shell policy and Kubernetes service account constrain what
the worker can inspect. Do not assume the worker has permission to mutate resources. A refused or failed tool call, including a Prometheus query
the server rejects or cannot answer, returns to the model as that tool's error with the reason (Prometheus's own
message for a rejected query), so the model can correct it; it does not fail the investigation.

The diagnosis includes evidence, proposed changes or manual actions, risk/confidence, verification,
and rollback where applicable. A plausible hypothesis without an actionable supported fix is
not a completed repair. SRE returns the decision; Sentinel owns execution.

## Apply a fix or request verification

Sentinel's incident fix publisher checks only what keeps agents away from secrets and the repository
boundary: paths must be repository-relative and content must not match its built-in credential
patterns. File changes carry paths and complete content, or `delete` with empty content to remove an
existing file (a directory is removed file by file, and a deletion that also carries content is rejected);
the executor stages deletions in the checkout and sends them to GitHub as tree entries without a blob. An empty PR title or body falls back to the
diagnosis summary and hypothesis. PR Review then reviews and merges the fix PR like any other, and attaches that review to the incident:
discovery matches the PR to the incident by its recorded URL, the incident keeps the review's ID (its detail links
to the review, and the review links back), and its timeline records `fix_review_started` and the review's final
status (`fix_review_blocked` with the reason, `fix_review_failed`, or `fix_review_merged`). These events never change
the incident's status: it stays `awaiting` until Alertmanager resolves the alert. The SRE prompt
requires secret-free changes. There are no path or resource-kind limits: a
fix may change any file and kind in the repository. A rejected proposal becomes blocked
with the reason in its hypothesis. Changes are grouped into one PR for the fix, even if several
files change. The workflow saves the result while the incident stays `running`, the same step that drops a
late result, and sends a `create-pull-request` command;
sentinel-executor checks the changes in a local checkout fetched with a short-lived GitHub App installation
token passed through Git config variables, has GitHub create the commit and branch through the Git Data API
(GitHub authors and signs the commit as the App, so it shows as verified), then creates the PR and
risk/confidence labels. Existing-PR
lookup avoids duplicate creation on repeated completion events; an identical fix whose PR was
closed without merging is blocked rather than reused. PR Review never auto-merges these branches.

Without a valid repository fix, the incident remains blocked. A diagnosis may instead offer
manual actions: operations the SRE agent cannot perform itself, such as cleaning up a stuck job,
restarting a workload, or reconciling or suspending a Flux object. The operator approves one; the
workflow claims it (bounded by `incident.manual_action_timeout_seconds`) and sends a
`run-command` command. sentinel-executor runs the approved command as a single argument vector
without a shell, subject to timeout and output limits in `infra/chart/sentinel/config/executor.yaml`.
Its `sentinel-executor` ClusterRole grants only specific Kubernetes operations and no Secrets,
RBAC, or CRDs. The workflow records the redacted, bounded result; an invalid command is
recorded as failed without running.
A successful manual action moves the incident to `awaiting` until Alertmanager resolves it. Approval is
not a bypass for the rule that infrastructure changes go through GitOps.

A model or tool outage during investigation (an unreachable or misconfigured LLM, or a reply
without a structured diagnosis) fails the incident with the error type in its hypothesis, so it
can be replayed. A failed incident stays failed until an operator replays it from the UI; its alert
firing again does not restart it. `blocked` is reserved for a completed diagnosis that found no safe fix.

## Replay and close

An operator can replay eligible incidents with new guidance. The workflow request carries only the incident
id and prompt; the prepare task loads a bounded replay context (the last five finished attempts with their
prompts, diagnoses, and errors) from PostgreSQL, and SRE assembles it inside its workflow. Every run is an
attempt kept with its own audit actions and tool budget, and nothing is trimmed; a replay of a running incident
marks the attempt it takes over `superseded` (`sentinel/core/src/sentinel/core/state/history.py`).
This is explicit replay context, not hidden cross-incident LLM memory. Replays must not inherit
another incident's response chain or obsolete approval controls.

Statuses say where the workflow is: `acknowledged` (queued), `reopened` (queued again after its alert
fired on a resolved or skipped incident), `running` (an investigation, including while sentinel-executor opens the fix
PR), `awaiting` (Sentinel opened a fix PR or a manual action succeeded; waiting for Alertmanager),
`blocked` (no safe fix, or a fix needing an operator), `failed`, `ignored` (an operator stopped tracking
it; alerts no longer requeue it), `skipped` (the alert had stopped firing when the workflow was about to
dispatch the run, so no investigation ran), and `resolved`, which only Alertmanager's resolved event sets. A run
still queued or running after `workflow_timeout_seconds` (the SRE run timeout, 30 minutes by default) fails as
`AgentTimedOut`, because nothing retries lost work; the SRE worker stops at the same deadline and anything it would
finish later is `RunTimedOut`; `awaiting` has no timeout. `awaiting`, `blocked`, and `failed` change only when the
alert resolves or an operator replays them from the UI; a firing alert reopens only a resolved or skipped
incident. `skipped` is not announced on Discord.

Sources: `sentinel/workflow/src/sentinel/workflow/sre/incidents/`,
`sentinel/sre/src/sentinel/sre/incidents/run.py`,
`sentinel/agents/src/sentinel/agents/sre/incident/agent.py`, `sentinel/agents/src/sentinel/agents/sre/incident/tools.py`, `sentinel/agents/src/sentinel/agents/sre/incident/commands.py`,
`sentinel/agents/src/sentinel/agents/sre/incident/prometheus.py`,
`sentinel/core/src/sentinel/core/domain.py`, `sentinel/console/ui/src/components/DomainView.tsx`.
