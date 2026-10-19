# Sentinel UI and operator action semantics

Repository: `sentinel`. Scope: management UI, refresh, and interpreting displayed records.

## Data and navigation

The `sentinel-ui` Deployment serves the built React/TypeScript UI from nginx; it calls the
`sentinel-api` Deployment on the same hostname under `/api`. Separate incident
and review workflows in sentinel-workflow consume Kafka, sentinel-executor performs their side effects, and agent
Deployments process commands; none of them serve UI traffic. The UI is one screen: a small
square per running agent (with its count of active workflows), and below it the selected
domain's workflow. The workflow view centers on that domain's state machine, drawn from
`GET /api/agents/{domain}/workflow` (the graph in `sentinel.core.state.workflows`): each state
shows how many loaded records it holds, clicking a state filters the records, and selecting a
record highlights its current state and the states its timeline passed through. Only forward transitions
(to a later column of the layout) are drawn as lines; every other transition is a note: under its target
when three or more states lead back into it (`← from 5 states · run started`), otherwise under its source
(`→ awaiting · manual action recorded`), and transitions from any state under their target. A selected or
current state labels its lines with their events, dims the other lines, and highlights the notes it takes part
in (`classifyTransitions` in `sentinel/ui/src/workflow.ts`).
The URL hash holds the selected domain and record (`#/sre/<incident id>`, `#/pr-review/<review id>`),
so a record can be linked and the browser or phone back gesture returns from a record to the list.
Below 860px the list and the detail share one column and a selected record replaces the list; below
640px the state machine is drawn top to bottom and its notes are listed under it.
Runtime configuration identifies the Sentinel API, and the displayed release version comes from
the backend rather than a separately hardcoded frontend version. `GET /api/agents` lists every
agent domain with `enabled` (from Sentinel configuration; each enabled agent has a dedicated worker Deployment)
and `running` (its worker's Kafka consumer group has active members, read through the API's `sentinel` Kafka user,
whose group Read includes Describe; `sentinel/core/src/sentinel/core/kafka/liveness.py`). Each agent tile's dot is
green while its agent is enabled and running and red when it is down or disabled; a disabled agent's tile cannot be
selected.

Hooks poll backend resources every five seconds while the page is visible, poll again when it
becomes visible, and support a manual refresh trigger. They are not a Kafka subscription or
server-pushed live stream. Empty filter results must remain distinguishable
from request failures; neither proves there are no records in the database. API list limits
mean displayed counts summarize the loaded records, not an unlimited database aggregate.

Resolved incidents are still records and are not deleted because a PR merged. The record detail
shows the incident or review facts, its pull request link, and the operator actions that apply to
its current state, followed by collapsible sections holding everything the record stores. An incident
shows its current diagnosis (hypothesis, evidence, validation, rollback, proposed files and changes, manual
actions), tool budget, timeline, attempts, and alert labels and annotations; manual-action runs include their
stdout and stderr. A review shows its current merge decision, findings, tool budget, checks with their output,
timeline, and attempts. The timeline lists every status change with its trigger, operator prompt, revision, and
reason. Attempts lists every agent run, newest first and never trimmed: its trigger (alert, review, replay, or
fix), operator prompt, revision, status, and result (an incident's diagnosis; a review's decision, findings, and
checks; a fix's changed files, its checks of the fixed revision, the pushed commit or why it was declined),
with its own tool budget and audit trail. The audit trail lists every model response with its token usage and
every tool call with its arguments and output. A record whose last agent run reached its tool budget carries a
"Tool budget reached" chip beside its status.

## Installing as an app

The UI is a progressive web app: `public/manifest.webmanifest` and its icons describe it, and the
build writes `sw.js` from `service-worker.js` with the list of every built file and a cache name
derived from their contents. The service worker precaches that shell, serves navigations from the
network and falls back to the cached shell offline, and never caches `/api`, so records are always
live; a new release replaces the worker and deletes the old cache. nginx serves `sw.js` and the
manifest uncached. Browsers offer installation only over HTTPS (Chrome and Edge "Install app",
Android "Add to Home screen", iOS Safari Share → "Add to Home Screen"). The PNG icons are rendered
from `public/favicon.svg`.

## Operator controls

Replay means the same in both domains: run the agent again as a new attempt, with optional operator guidance
and the record's earlier attempts as context; earlier attempts are kept, never overwritten.
Manual-action approval runs a specific proposed command through sentinel-executor. Manual actions
change the cluster (for example deleting a stuck job or restarting a workload), so inspect the
command before approving: approval is a real external action. The executor runs the approved
command without a shell, subject to its timeout, output, and Kubernetes permission limits.
Ignore and Delete queue requests for the workflow to apply. Ignore changes tracking state;
Delete removes the PostgreSQL row and its stored history after the request is consumed.
A later alert or discovery of the same PR can create a new record. Deletion does
not resolve the upstream alert or undo a PR. Review Check now triggers
discovery. Review Replay accepts blocked, failed, running, and fixing reviews: the workflow reads the PR from
GitHub, records a merge that already happened, explains a closed PR on the review, and otherwise reviews its
current revision again. Fix it appears only on blocked reviews: the reviewer receives the earlier attempts and
the optional operator instruction, returns complete new contents of the files it changes, and checks the fixed
revision; Sentinel pushes one commit to the PR's own branch only when the checks pass and the changes are
repository-relative and credential-free, and the next discovery reviews the new head as another attempt. Fix it
is declined, and the review stays blocked with the reason, when the PR is closed, changed since its review, or
comes from a fork. Deleting a review does not close or revert its GitHub PR.

The API has no authentication; access is limited by network reach (the internal gateway route
and NetworkPolicies). UI disable states improve interaction but are not a security boundary.
Diagnose stale head SHA, schema errors,
and network failures from the backend response rather than assuming a button silently succeeded.

Sources: `sentinel/ui/src/main.tsx`, `sentinel/ui/src/App.tsx`, `sentinel/ui/service-worker.js`, `sentinel/ui/vite.config.ts`, `sentinel/ui/src/hooks/`, `sentinel/ui/src/api/`,
`sentinel/ui/src/components/`, `sentinel/api/src/sentinel/api/server.py`,
`sentinel/api/src/sentinel/api/routes/sre.py`, `sentinel/api/src/sentinel/api/routes/pr_review.py`.
