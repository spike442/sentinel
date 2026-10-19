# Homelab GitOps change and review procedure

Repository: `homelab`. Scope: locating a safe change and proving reconciliation.

## Trace the owning declaration

Start with the alert's namespace, resource kind/name, and controller owner references. Find the
application's Flux `ks.yaml`, its Kustomize resource list, and then the Helm values or native
manifest that owns the affected field. Shared components under `kubernetes/components/` can
affect several applications; search their consumers before editing them.

Trace the chain from Git source to Flux Kustomization to HelmRelease or workload. An operator
may generate the failing resource from a higher-level custom resource. Change the owner,
not generated objects or status fields. For Helm resources, check the actual chart values
schema before introducing a property; a syntactically valid unknown value may do nothing.

## Desired state versus applied state

If the fix already exists in the current default branch, compare that revision with the source
artifact and the Kustomization's applied revision. Check suspended sources/controllers,
dependency readiness, Helm failures, schema errors, and missing secrets. Do not create a
duplicate PR that merely restates an already-correct declaration.

A useful change report states the failing behavior, evidence, owning source path, proposed
change, blast radius, verification, and rollback. A merged PR is not proof of recovery.
Alert resolution remains a separate observation from the monitoring system.

## Validation and risk

Render the smallest affected Kustomization and its prerequisites. `kubectl kustomize <path>`
builds locally; it does not apply. Flux substitution and chart rendering may require additional
repository tooling. Check resource references, namespace, storage bindings, image/version
coherence, CRD availability, and dependency graph. `git diff --check` finds whitespace errors,
not semantic Kubernetes errors.

Treat changes to persistent volumes, reclaim policies, namespaces, RBAC, Secret mappings,
Kafka retention/ACLs, database ownership, and shared backup components as wider-impact changes.
Never remove data-bearing declarations simply to silence an alert.

Repository Taskfiles include powerful operator commands such as apply, delete, reconcile,
bootstrap, node debugging, pruning, and secret inspection. Their existence is not authorization
for an agent to run them. Routine agent remediation stays GitOps; diagnostic reads should be
narrow and avoid Secret values.

Sources: `kubernetes/flux/cluster/ks.yaml`, `kubernetes/components/`,
`.taskfiles/Kubernetes/Taskfile.yaml`, `.pre-commit-config.yaml`, `.github/workflows/`.
