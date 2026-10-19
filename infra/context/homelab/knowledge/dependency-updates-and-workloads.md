# Homelab dependency updates and stateful application diagnosis

Repository: `homelab`. Scope: Renovate review and recurring workload failure patterns.

## Dependency automation

Renovate discovers Kubernetes images, Helm/Flux declarations, GitHub Actions, pre-commit hooks,
Ansible collections, and NAS Docker Compose dependencies through repository configuration.
Shared rule files define grouping, labels, semantic commit messages, and automerge. Some
non-major updates can merge after checks; trusted action rules also have branch-automerge
exceptions. Do not assume every change waits for Sentinel PR review or that every automerge rule
requires identical checks. Read the effective rule for the dependency being reviewed.

A dependency PR should change the intended artifact and any required paired values/locks/digests.
Grouped updates can be deliberate; unrelated edits still need explanation. A chart bump can
change generated resources, defaults, CRDs, or persistence behavior even when the manifest diff
is tiny. A mutable image tag can change running code without a new literal tag in Git.
Digest pinning, application compatibility, rollback behavior, and upstream release notes are
separate evidence requirements. Bot authorship is not evidence of safety.

## Nextcloud and scheduled jobs

Nextcloud has a web workload and a CronJob, with database, Valkey, Secret, and mounted persistent
data dependencies. A failed cron Job is a symptom: inspect its actual command, image coherence
with the web workload, application bootstrap state, credentials references, mounted configuration,
filesystem identity, database/cache reachability, and logs. Deleting the failed Job does not
repair the next scheduled execution and loses diagnostic evidence.

The application uses distinct persistent mounts for configuration/files/apps. Trace the specific
PVC and backup policy before proposing storage changes. A successful /status.php probe does
not prove background tasks completed or all database/filesystem operations work.

## Media applications and node-specific capabilities

Media applications may combine local configuration PVCs with NAS media mounts and separate
backup policies. For youtubedl, inspect configuration and media mounts independently; stale
configuration backup and unavailable media storage are different failures. A Service may expose
both LAN load-balancer access and an HTTPRoute, which can fail independently.

GPU driver components involve privileged node integration and host/container interface paths.
Do not treat a GPU issue as an ordinary image-only application upgrade or assume every node has
the same hardware. Read resource claims, driver declarations, node placement, and workload
requirements before changing scheduling or security context.

Sources: `.renovaterc.json5`, `.renovate/autoMerge.json5`, `.renovate/packageGroups.json5`,
`kubernetes/apps/productivity/nextcloud/app/helmrelease.yaml`,
`kubernetes/apps/productivity/nextcloud/database/`,
`kubernetes/apps/media/youtubedl/app/helmrelease.yaml`,
`kubernetes/apps/kube-system/intel-gpu-resource-driver/app/helmrelease.yaml`.
