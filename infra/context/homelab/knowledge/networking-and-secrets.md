# Homelab networking, service access, and secrets

Repository: `homelab`. Scope: connectivity diagnosis and credential boundaries.

## Request path

For external HTTP access, follow DNS to the Envoy Gateway address, the Gateway listener,
matching HTTPRoute hostname/path, backend Service port, EndpointSlice, and ready workload.
Cilium advertises configured load-balancer addresses on the LAN. Envoy's certificate references
and listener route permissions can block traffic independently of application health.

For service-to-service calls, use configured cluster-local Service DNS rather than the public
HTTPRoute. A public URL failing does not prove that a backend process is down, and working
Pod health does not prove DNS or ingress works. Inspect selectors, named ports, targetPorts,
readiness, namespace references, and backend route conditions before changing application code.

Pi-hole is deployed outside Kubernetes through Ansible-managed Docker Compose on the NAS;
Kubernetes has related DNS integrations. Distinguish authoritative DNS configuration, client
resolver/cache behavior, CoreDNS, and ingress routing. Read current addresses from configuration
rather than carrying LAN IPs in knowledge documents.

## Secret delivery

The `onepassword` ClusterSecretStore uses 1Password Connect. ExternalSecret manifests map vault
items and properties into Kubernetes Secret keys; Deployments consume those keys via explicit
references or mounts. A remote property name, generated Secret key, and application environment
variable can differ. Trace all three instead of assuming that renaming one updates the others.

Inspect ExternalSecret Ready conditions, Secret existence, and reference names without printing
credential contents. RBAC, pod identity, filesystem permissions, and application configuration
are separate failure layers. Never copy Secret values into PRs, knowledge, logs, or screenshots.

Sentinel uses one GitHub App for checkouts, commits, and API operations: checkouts run over HTTPS with a
short-lived installation token passed through Git config variables, and fix commits are created through the
GitHub API, which signs them as the App, so there is no SSH deploy or signing key.
A refused commit or branch usually means the App lacks contents write permission on the repository.

Sources: `kubernetes/apps/kube-system/cilium/app/networking.yaml`,
`kubernetes/apps/network/envoy-gateway/app/envoy.yaml`,
`kubernetes/apps/network/pihole-dns/`, `ansible/roles/pihole/`,
`kubernetes/apps/external-secrets/onepassword/app/clustersecretstore.yaml`,
`kubernetes/apps/agents/sentinel/app/helmrelease.yaml`, `kubernetes/apps/agents/sentinel/app/externalsecret.yaml`.
