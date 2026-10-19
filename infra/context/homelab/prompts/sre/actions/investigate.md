
Investigate the alert with the fewest targeted tool calls that establish the cause. Correlate the
alert with current live state, metrics, the synchronized repository, and relevant public
documentation. Identify the owning desired-state file before proposing a change.

If the desired state is already correct, inspect reconciliation or live-state drift and report the
evidence; do not invent a no-op PR or bypass GitOps. If a repository fix is supported, provide the
complete change. Otherwise, provide exact read-only verification actions when they can resolve a
specific uncertainty; use a blocked result when no actionable step is supported.

Do not reject a concrete validated fix solely due to its risk or confidence level; report both
accurately.
