# Homelab monitoring and incident triage

Repository: `homelab`. Scope: alert origin, routing, and evidence collection.

## Monitoring responsibilities

Prometheus evaluates metric rules; Alertmanager groups and inhibits notifications. Gatus checks
application endpoints and submits alerts to Alertmanager's API. Its sidecar discovers supported
Service/HTTPRoute annotations, so not every endpoint is handwritten in the base Gatus config.
Grafana displays data. Fluent Bit ships logs to VictoriaLogs. Flux notifications are a separate
controller-event path; they are not the same as Prometheus alert evaluation.

Alertmanager's `sentinel` webhook receiver posts every alert, ungrouped and with resolutions, to the Sentinel API
(`sentinel-api`, `/api/sre/events/alertmanager`), which publishes each alert to `sentinel.cluster.alerts`; Alertmanager
holds no Kafka credentials. Alertmanager itself does not post to Discord. Sentinel does: when an incident or review
reaches a terminal status, sentinel-executor posts one message through the `DISCORD_WEBHOOK_URL` webhook.
Sentinel ingests alerts, dispatches investigations, and stores decisions.
Gatus-origin labels let Sentinel distinguish endpoint alerts after Alertmanager
normalization. A configured `send-on-resolved` flag alone does not prove the downstream payload
has the expected resolved status: inspect the Sentinel API logs for the posted notification if recovery is not reflected.

## Targeted investigation

Begin with alert identity, labels, annotations, start/end times, status, and query when available.
For a workload failure, inspect its controller, conditions, recent events, relevant container
logs, dependencies, and owning Git declaration. For an endpoint failure, compare in-cluster
Service health with DNS/Gateway behavior. For backups, compare schedule, last success, policy,
repository, and mover evidence. Query only the metrics or resources needed for the hypothesis.

Do not ship the entire cluster state to an LLM or call a resource healthy because its Pod exists.
Separate missing configuration, bad desired state, stale Flux revision, and live dependency
failure. Evidence should identify the layer that fails and the smallest corrective declaration.

## Delivery and resolution diagnosis

If an alert is missing, trace metric/rule or Gatus detection, Alertmanager active alerts/event
recording, `sentinel.cluster.alerts`, incident workflow and persisted incident, SRE command and return
topics, agent worker execution, sentinel-executor returns for pull requests and manual actions, and stored decision. Notification failure is different from
investigation failure.

Sentinel marks matching incidents resolved when an incoming alert says resolved.
A created or merged PR does not resolve an incident by itself. Preserve the fingerprint and
source across firing and recovery events so they match the same incident.

Sources: `kubernetes/apps/observability/kube-prometheus-stack/app/alertmanager-secret.yaml`,
`kubernetes/apps/observability/gatus/app/resources/config.yaml`,
`kubernetes/apps/observability/gatus/app/helmrelease.yaml`,
`kubernetes/components/alerts/`, `kubernetes/apps/observability/fluent-bit/`,
`kubernetes/apps/observability/victoria-logs/`.
