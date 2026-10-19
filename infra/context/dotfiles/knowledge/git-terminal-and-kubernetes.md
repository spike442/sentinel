# Dotfiles Git, terminal sessions, and Kubernetes console

Repository: `dotfiles`. Scope: interactive developer tools and security boundaries.

## Git behavior

The Git configuration enables SSH-format commit signing and points to a user signing public
key. Cryptographic signing requires the corresponding accessible private key/agent. Commit
sign-off and commit signing are different features. Neither establishes GitHub push permissions.

Push URL rewriting can turn a GitHub HTTPS URL into SSH transport for pushes; fetch and push
authentication can therefore differ. Pull uses rebase and upstream setup is automated. Before
diagnosing publickey errors, inspect effective remote fetch/push URLs and SSH identity selection.
Do not copy the user's email or key material into the knowledge base or a bot deployment.

Aliases/functions include force-push and working-tree restore operations. They are personal
shortcuts, not safe defaults for an autonomous agent. In particular, force-pushing main or
amending staged-all changes can rewrite or publish unrelated work.

## WezTerm

WezTerm loads configuration from `.config/wezterm/wezterm.lua`, with a local background image,
font choice, and custom tab-title behavior. It loads a session-resurrection plugin from a
remote Git repository; that URL is not a pinned commit in this configuration. Session save and
restore shortcuts and GUI startup restoration depend on the plugin and local saved state.

Saved terminal sessions and scrollback may contain credentials or private commands. Do not
ingest them into RAG, attach them to issues, or treat them as configuration source. A font or
plugin failure is a workstation issue, not a Kubernetes application failure.

## k9s

k9s config and resource aliases live under `.config/k9s/`, with a transparent skin and log-view
preferences. The configured console is not read-only; its effective authority comes from the
selected kubeconfig context and Kubernetes RBAC. A namespace shown in the UI is not an access
boundary. Debug shell features can create workloads and are state-changing.

For safe diagnosis, verify the current context and namespace, inspect resources/logs narrowly,
and avoid Secret value views or mutation commands. Agents must follow Homelab's GitOps policy
even if a human's workstation credentials could perform imperative changes.

Sources: `.config/git/config`, `.config/git/ignore`, `.config/wezterm/wezterm.lua`,
`.config/k9s/config.yaml`, `.config/k9s/aliases.yaml`,
`.config/k9s/skins/dracula-transparent.yaml`.
