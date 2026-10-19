# Homelab storage, backups, and recovery reasoning

Repository: `homelab`. Scope: storage ownership and backup investigation.

## Storage classes and data ownership

OpenEBS local volumes are tied to host storage; they are not replicated network volumes.
Before proposing rescheduling or PVC replacement, inspect PV node affinity, storage class,
claim binding, reclaim policy, mount paths, and workload access mode. A new Pod does not imply
that an old local volume can move to another host.

NAS-backed NFS volumes and local application configuration volumes have different ownership
and recovery paths. An application may use NAS media alongside a local configuration PVC.
Identify which volume is failing rather than treating all mounts as one dataset. Persistent
data cannot be made safe merely by setting the Deployment replica count back to one.

## Kopiur backup model

The shared backup component defines a SnapshotPolicy and SnapshotSchedule for an application's
PVC. A ClusterRepository defines the NAS-backed repository, encryption Secret references,
namespace access, and server/bootstrap behavior. A Ready repository alone does not establish
that any application backup succeeded.

For a stale-backup alert, compare the alert expression with the policy's last successful
snapshot, the schedule's last/next run, recent Snapshot conditions, and repository readiness.
Distinguish a schedule slower than the alert threshold from execution failure, missing policy,
deleted success records, a stuck mover, or a repository/bootstrap problem. Check both current
Git declarations and applied controller state before proposing a cadence change.

Retention controls recovery points, not execution success. `runOnCreate` behavior and shared
component edits can affect many PVCs. Verify identity, volume permissions, projected credentials,
NAS availability, and sufficient disk space before changing backup policy.

## Recovery boundaries

Kafka uses a persistent single-node pool and a separate Kopiur backup Kustomization. This gives
a recovery mechanism, not broker high availability. A filesystem backup must have a tested
Kafka recovery procedure and consistency expectations; a declared schedule is not proof of
a usable restore. PostgreSQL has its own CloudNativePG/Barman backup path to object storage,
not an interchangeable arbitrary PVC restore.

Never delete/recreate PVs, PVCs, repository data, or backup records to clear symptoms. Recovery
requires owner-approved recovery point and data-loss decisions, then the appropriate GitOps
declarations. Do not claim a restore is proven without an actual restore exercise.

Sources: `kubernetes/apps/storage/openebs/`, `kubernetes/components/backup/snapshot-policy.yaml`,
`kubernetes/apps/backups/kopiur/app/repository.yaml`,
`kubernetes/apps/backups/kopiur/app/prometheusrule.yaml`,
`kubernetes/apps/messaging/kafka/backup/`,
`kubernetes/apps/database/cloudnative-pg/cluster/cluster.yaml`.
