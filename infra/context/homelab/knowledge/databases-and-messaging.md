# Homelab PostgreSQL, Kafka, and object storage

Repository: `homelab`. Scope: infrastructure versus application setup ownership.

## PostgreSQL

CloudNativePG manages the PostgreSQL cluster, storage, monitoring, and Barman backups. Its
read/write Service is the internal connection target; external access has a separate route.
An application database declaration belongs with that application's GitOps resources, not
as an unrelated application in the database platform folder.

Sentinel's PostgreSQL database definition declares its owner and holds incident and review state.
CloudNativePG provisions the database and role; Sentinel's separate SQL script creates application
tables. These are different steps: a successful database resource does not imply the schema
has been applied. Worker agents do not need PostgreSQL credentials.

Sentinel's PostgreSQL tables store operator-facing incident and review state. Kafka topics
carry requests, commands, returns, and outcome events.

## ClickHouse and local embeddings

The ClickHouse platform app owns its server, volumes, and administrative account. Sentinel owns
its native backup schedule; Sentinel's `task deploy` creates its database and user and applies its
schema before application rollout. Alert evidence and
the knowledge index live in ClickHouse. Sentinel's knowledge Pod runs the
pinned ONNX model in process for both search and periodic indexing. Sentinel owns
chunking and retrieval; agent workers receive excerpts rather than database credentials.
Kopiur copies native backups from a dedicated PVC off-node. Single-node storage provides
recovery from backup rather than automatic failover.

## Kafka platform and application resources

Strimzi manages a KRaft Kafka cluster and a persistent KafkaNodePool with combined broker and
controller roles. The configured single broker cannot tolerate broker/host loss without
interruption. PVC retention and Kopiur backups support recovery; they do not provide replication
or automatically replay deleted topic history from S3.

The Kafka platform folder owns the operator, cluster, node pool, and backup integration. Sentinel is
the only agent application using Kafka, with its user/ACLs in `sentinel/infra/kafka.yaml`. Its
incident workflow consumes Alertmanager events (forwarded by the Sentinel API) from `sentinel.cluster.alerts` and logs invalid messages before committing them.
Workflow, agents, and sentinel-executor exchange requests, commands, and returns on Kafka topics. The Sentinel chart declares
those topics (partitions, retention, cleanup policy); Homelab declares the users and ACLs.
Auto topic creation is disabled; producer code cannot substitute for topic provisioning.

The internal application listener uses SCRAM authentication without TLS and is the only listener;
Alertmanager reaches Kafka through the Sentinel API, not directly. Current cluster configuration also permits
access when no ACL matches; do not describe this as a TLS-protected, universally deny-by-default
broker. Read the cluster listener/auth configuration and app KafkaUser ACLs before changing
permissions or diagnosing authorization failures.

Consumer group identity, topic permissions, broker connectivity, offsets, and publish delivery
confirmation are separate concerns. Kafka durability does not make a PostgreSQL write and a
message publication atomic. Topic retention is not an indefinite incident archive.

Sentinel publishes saved incident and review records to `sentinel.workflow.outcomes` when a
workflow finishes. An operator-managed Spark query reads that topic and archives the
messages to S3. It does not write to ClickHouse. Sentinel remains responsible for canonical
incident state. Publishing is not atomic with the database commit;
monitor failed result handling for missing outcome messages.

## Object storage

RustFS provides S3-compatible object storage with a cluster-local Service and a separate web
route. Consumers include database backups and agent prompts/knowledge. Browser console login,
S3 endpoint, access key, and secret access key are distinct configuration concepts. A valid
console session does not prove request signatures are correct. Check exact credential values,
endpoint, region, path-style addressing, and clock before blaming bucket existence.

Sources: `kubernetes/apps/database/cloudnative-pg/cluster/`,
`kubernetes/apps/agents/sentinel/infra/database.yaml`, `kubernetes/apps/messaging/kafka/app/cluster.yaml`,
`kubernetes/apps/messaging/kafka/app/nodepool.yaml`,
`kubernetes/apps/agents/sentinel/infra/kafka.yaml`, `kubernetes/apps/storage/rustfs/`.
