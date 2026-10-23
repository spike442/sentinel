# Homelab bootstrap and agent deployment dependencies

Repository: `homelab`. Scope: host/bootstrap boundaries and Sentinel rollout prerequisites.

## Host preparation versus reconciliation

Ansible inventory/group variables describe machines and K3s settings. OS roles configure host
packages, filesystems, networking, time, firewall, and SSH. Kubernetes playbooks prepare/install
K3s. Bootstrap Helmfile and resources establish controllers required before Flux can reconcile
the application tree. These privileged installation operations are operator workflows, not
incident-remediation tools for an LLM.

Pi-hole has a separate Ansible role and Docker Compose lifecycle on the NAS. A failure there
is not repaired by restarting a similarly named Kubernetes integration. Avoid commands that
print decrypted credentials or reset passwords into logs.

## Agent application layout

Sentinel, SRE, PR Review, and embeddings are deployed as one chart in the `agents` namespace. Sentinel owns their
GitOps support resources, PostgreSQL database and roles, and its Kafka users and ACLs.
Flux dependencies connect prerequisite Kustomizations to the application; keep setup with its
owner rather than introducing separate platform applications for app-specific credentials.

Sentinel's main app serves both backend and built UI. The `sentinel-sre` Deployment (one container
running both SRE agents) consumes Kafka commands; Workflow consumes incident and review requests and returns. Service accounts,
ClusterRoles, projected tokens, kubeconfig mounts, and HOME are deployment concerns.
Both agent roles are read-only. sentinel-executor's ClusterRole may delete jobs and pods, restart
workloads, and patch Flux objects for approved manual actions, and grants no Secrets, RBAC, or
CRDs; none of these permission sets should be called cluster-admin.
The chart in `infra/chart/sentinel/` renders Sentinel's API, Workflow, sentinel-executor, knowledge API, process
configuration, SRE, and PR Review in the agents namespace. Homelab's
`sentinel/app` keeps the Flux HelmRelease, OCIRepository, and the centralized ExternalSecret
definitions; `sentinel/infra` keeps the cross-namespace resources Sentinel needs: PostgreSQL database and roles,
and Kafka users with their ACLs. Its values point to external services
and name existing Secrets, database roles, Kafka users, and consumer groups; the Sentinel chart creates its
own Kafka topics. The chart
renders those values into Sentinel configuration; other site configuration lives in the
Sentinel chart's `config/` files. Namespace-local Secret projections are still needed
for the database and messaging operators.

## Rollout proof

Before rollout, verify required CRDs/operators and SecretStore health, then run Sentinel's
`task deploy` once the PostgreSQL database and roles and the ClickHouse server exist. Verify
the Sentinel chart's Kafka request, command, and return topics, Homelab's Kafka users/ACLs, prompt objects/checksum,
the knowledge image with its pinned model, and image tags.
Database creation is not schema initialization. Prompt upload is not knowledge
indexing. Image publication is not Flux deployment.

After GitOps reconciliation, check dependency conditions, Deployment rollout, pod events,
startup logs, workflow and agent worker readiness, Sentinel Kafka ingress, Sentinel's health/version response,
and UI API access. Test one real event before broad replay. Agent images run as long-lived
Kafka consumers. Current image versions and replicas must be read
from manifests, not this document.

Sentinel API, Workflow, sentinel-executor, and the agents use different subsets of the `sentinel-secrets`
ExternalSecret. Do not remove a key merely because one Deployment does not consume it: another
Deployment or a worker may still require it. The local SQL task reads its database
passwords directly from 1Password. Compare
each `secretKeyRef` and projected volume item with the ExternalSecret and the corresponding
settings or entrypoint. SRE and PR Review credentials are projected into the agents namespace
by the central Sentinel ExternalSecret. Their worker pods read only the keys they need.
No database or GitHub credentials are mounted into those workers.

Sources: `ansible/playbooks/kubernetes/`, `ansible/roles/os/`, `ansible/roles/pihole/`,
`bootstrap/helmfile.d/`, `kubernetes/apps/agents/sentinel/ks.yaml`,
`kubernetes/apps/agents/sentinel/app/`, `kubernetes/apps/agents/sentinel/infra/`,
`infra/chart/sentinel/`.
