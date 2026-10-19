# Homelab architecture and ownership

Repository: `homelab`. Scope: stable desired-state architecture, not deployed inventory.

## Source of truth and layers

Homelab is a K3s installation managed through GitOps. `ansible/` manages host preparation and
installation; `bootstrap/` installs prerequisites before normal reconciliation;
`kubernetes/` declares cluster services and applications. A NAS also hosts storage and services
outside Kubernetes. An application can depend on both Kubernetes and external host systems.

Flux reconciles the repository into Kubernetes. A file on the default branch describes desired
state; it does not prove that the corresponding controller has applied it. Inspect the Flux
source revision, Kustomization conditions, HelmRelease conditions, and workload events to
establish the applied state. A directory alone is not proof that an application is enabled.

## Application structure

Namespace directories under `kubernetes/apps/` compose application resources. Applications
normally have `ks.yaml` defining Flux Kustomizations and an `app/kustomization.yaml` listing
native manifests or HelmRelease/chart sources. Some split prerequisites into `database/`,
`kafka/`, or `backup/` with their own Flux Kustomizations. Kubernetes `Kustomization` resource
lists and Flux `Kustomization` custom resources serve different purposes.

`dependsOn` defines reconciliation ordering, not the order of YAML documents or directory names.
Check health checks, `wait`, source references, target namespace, post-build substitutions,
and pruning together. Removing a tracked declaration can delete a resource during pruning.

## Platform responsibilities

Cilium supplies cluster networking and LAN load-balancer advertisement. Envoy Gateway handles
Gateway API routing. External Secrets connects applications to 1Password. OpenEBS supplies
local volumes; NAS-backed volumes provide external storage. RustFS offers S3-compatible object
storage. CloudNativePG manages PostgreSQL. Strimzi manages Kafka. Sentinel's Workflow
process and agents use Kafka for workflow delivery. Kopiur manages filesystem
backups. Prometheus, Alertmanager, Gatus, Grafana, Fluent Bit, and VictoriaLogs provide distinct
monitoring and logging functions.

Sentinel is an application on this platform, not its infrastructure operator. It owns agent
orchestration, incident/review persistence, approved decision execution, and the UI. Workers
investigate or review and return decisions. Cluster changes must be repository changes
reconciled by Flux, not imperative fixes from an agent shell.

Sources: `kubernetes/flux/cluster/ks.yaml`,
`kubernetes/apps/flux-system/flux-instance/app/helmrelease.yaml`,
`kubernetes/apps/agents/kustomization.yaml`, `ansible/`, `bootstrap/`.
