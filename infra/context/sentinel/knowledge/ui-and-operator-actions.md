# Sentinel UI and operator action semantics

Repository: `sentinel`. Scope: management UI, refresh, and interpreting displayed records.

## Data and navigation

The `sentinel-ui` Deployment serves the built React/TypeScript UI from nginx. The UI knows no domain in advance: it
reads `/domains.json` (rendered from the Sentinel chart's `console.domains`, mounted over the built default, and served
uncached), a list of domains each with its tile icon (kept while its backend is unreachable) and the base path of its own
backend on the same hostname: `/api/sre` (`sentinel-api`) and `/api/stonks` (`stonks-api`, routed by the Stonks
chart). Adding a domain
is one entry there and a backend serving the console contract (`AGENTS.md`). Separate incident and review workflows
in sentinel-workflow consume Kafka, sentinel-executor performs their side effects, and agent Deployments process
commands; none of them serve UI traffic.

The UI is one screen: a small square per listed domain, and below it the selected domain. Each square comes from
that domain's `GET manifest`: its label and icon (SRE the Kubernetes wheel, Stonks the charging bull, in one line style),
`enabled` (SRE from Sentinel configuration),
`running` (for SRE, both agents' workers have Kafka consumer groups with active members, read through the API's `sentinel`
Kafka user, whose group Read includes Describe; `sentinel/core/src/sentinel/core/kafka/liveness.py`), and for a
workflow domain its count of records in an active or waiting state. Its dot is green while the domain is enabled
and running and red otherwise; a disabled domain, or one whose backend does not answer, cannot be selected, and the
others keep working. The release version shown is the selected domain's manifest version.

A `workflow` domain lists its workflows as tabs, each with its agent's live dot and active count: SRE has
Incidents (the SRE agent) and Reviews (the PR Review agent). The selected workflow centers on its state machine, drawn from its `GET workflow` (the graph in
`sentinel.core.state.workflows`, with each state's tone from the domain's backend): each state shows how many loaded
records it holds, clicking a state filters the records, and selecting a record highlights its current state and the
states its timeline passed through. Only forward transitions (to a later column of the layout) are drawn as lines;
every other transition is a note: under its target when three or more states lead back into it
(`← from 5 states · run started`), otherwise under its source (`→ awaiting · manual action recorded`), and
transitions from any state under their target. A selected or current state labels its lines with their events,
dims the other lines, and highlights the notes it takes part in (`classifyTransitions` in
`sentinel/console/ui/src/workflow.ts`). The buttons on a record are the `actions` its backend lists for the
record's current status, with their prompt and confirmation; the backend refuses any other action. A record's
`links` open a related record in another domain (an incident's Fix review, a fix review's Incident). A domain
with its own record view in `src/domains/<id>/` renders the record's facts; any other domain gets a generic view
with the record's timeline, attempts, and stored JSON. A workflow's header carries Refresh and the events its UI
module offers (Reviews: Check now).

A `data` domain (Stonks) lists its datasets as tabs (universe, rejections, candidates, dividend dates, bar
watermarks, Yahoo symbols, countries) and shows the selected one as a grid of its JSON rows: one column per key,
nested values as JSON, sortable by clicking a column, filtered by a text box, and for trade-dated datasets a trade
date selector that defaults to the latest universe. It reads S3 through `stonks-api` and changes nothing.

The URL hash holds the selected domain and record or dataset (`#/sre/incidents/<incident id>`, `#/sre/reviews/<review id>`,
`#/stonks/universe`), so a record can be linked and the browser or phone back gesture returns from a record to
the list. Below 860px the list and the detail share one column and a selected record replaces the list; below
640px the state machine is drawn top to bottom and its notes are listed under it, and a dataset grid scrolls
within its panel.

Manifests and workflow records are polled every five seconds while the page is visible, polled again when it
becomes visible, and refreshed by Refresh; datasets load on selection and on Refresh. They are not a Kafka subscription or
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
network and falls back to the cached shell offline, and never caches `/api` or `/domains.json`, so records and the domain list are always
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
discovery (`POST /api/sre/events/check`). Review Replay accepts blocked, failed, running, and fixing reviews: the workflow reads the PR from
GitHub, records a merge that already happened, explains a closed PR on the review, and otherwise reviews its
current revision again. Fix it appears only on blocked reviews: the reviewer receives the earlier attempts and
the optional operator instruction, returns complete new contents of the files it changes (or deletes them), and checks the fixed
revision; Sentinel pushes one commit to the PR's own branch only when the checks pass and the changes are
repository-relative and credential-free, and the next discovery reviews the new head as another attempt. Fix it
is declined, and the review stays blocked with the reason, when the PR is closed, changed since its review, or
comes from a fork. Deleting a review does not close or revert its GitHub PR.

The API has no authentication; access is limited by network reach (the internal gateway route
and NetworkPolicies). UI disable states improve interaction but are not a security boundary.
Diagnose stale head SHA, schema errors,
and network failures from the backend response rather than assuming a button silently succeeded.

Sources: `sentinel/console/ui/src/main.tsx`, `sentinel/console/ui/src/App.tsx`, `sentinel/console/ui/public/domains.json`,
`sentinel/console/ui/service-worker.js`, `sentinel/console/ui/vite.config.ts`, `sentinel/console/ui/src/hooks/`,
`sentinel/console/ui/src/api/`, `sentinel/console/ui/src/components/`, `sentinel/console/ui/src/domains/`,
`sentinel/console/api/src/sentinel/api/server.py`, `sentinel/console/api/src/sentinel/api/domains/`,
`sentinel/stonks/api/src/stonks/api/`, `infra/chart/sentinel/templates/ui/`, `infra/chart/stonks/templates/api/`.
