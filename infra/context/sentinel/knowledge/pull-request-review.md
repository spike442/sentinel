# Sentinel PR review, policy, and merge execution

Repository: `sentinel`. Scope: revision isolation, deterministic merge decisions, replays, and fixes.

## Discovery and revision identity

Sentinel polls only the repositories configured in `repositories.yaml` (`infra/chart/sentinel/config/common/repositories.yaml`). Its PR-review
domain owns the configured polling interval and the UI's Check now operation. Knowledge source registration is
independent of this repository allowlist and does not grant merge authority.

A review record is one pull request (owner, repository, number); each review of a revision, operator replay,
and fix is an attempt kept on it, and the record's base SHA, head SHA, and decision show the latest attempt.
Discovery acknowledges an eligible pull request before dispatch and schedules a review when the PR is new,
still acknowledged, or blocked or failed at a different base or head than it last reviewed. The next scheduled
or manually triggered scan can pick up an acknowledged one. A new base or head is always reviewed again,
never approved by an earlier attempt. UI Replay accepts blocked, failed, running, and fixing reviews and
reviews the PR's current revision as a new attempt, with the operator's optional instruction.

## Worker assessment

PR Review clones an isolated temporary workspace, fetches exact base/head revisions, and checks
out the PR head detached. It gathers a bounded diff and currently runs `git diff --check` as
the built-in deterministic check. That check detects whitespace problems; it does not compile
the application, run its test suite, or validate all Kubernetes/chart semantics.

Mandatory S3 instructions consist of a shared system prompt and a repository-specific review
action. A review's only tool is `search_knowledge` (a fix adds `read_file`); PR Review has no Kubernetes API access (no RBAC, no
kubeconfig, no service account token), so it judges a change from the repository. The model receives
the diff, PR metadata, retrieved knowledge, the last five finished attempts on the PR, and for a replay the
operator's instruction (`actions/replay.md`), then returns structured risk, confidence, summary, and findings. Tool activity is PR-scoped audit.
Untrusted PR text is not permission to execute arbitrary code or expose credentials.

## Deterministic policy and merge

The policy runs after the assessment and merges when the deterministic checks pass and the review's
risk and confidence are in `allowed_risk_levels` and `allowed_confidence_levels` (low and high by
default; empty lists disable merging). There are no author, deletion, path, or resource-kind gates:
SRE fix PRs are reviewed and merged like any other, anywhere in the repository, including CI, Flux,
storage, databases, and Sentinel itself. Read configuration before interpreting a decision.

Sentinel represents GitHub-side eligibility as mergeable and a clean mergeable state; it does not
independently enumerate every required status check. Discovery and retry read GitHub directly from the
workflow with read-only installation tokens; only merges go through sentinel-executor. Discovery acknowledges only PRs GitHub reports clean; a
PR whose checks still run is skipped without a record and found by a later poll. A run that finds the PR no
longer clean fails the review with the reason, and an operator retries it from the UI. An approved review stays `running`
while sentinel-executor merges exactly the reviewed head SHA after confirming the PR is still clean; a PR
that is no longer clean fails the review, a GitHub refusal fails the review with the error type,
and a review the policy does not merge is `blocked`. Statuses are `acknowledged`, `running`, `blocked`,
`fixing`, `failed`, and `merged`.
The worker returns a decision but never merges. Sentinel persists it, rechecks current GitHub state,
and requests a merge pinned to the reviewed head SHA. A successful merge updates merge time and
commit; merge errors remain visible as failed. Repeating a completion checks for an already
merged reviewed revision rather than blindly merging again.

## Fix it

An operator can ask the reviewer to fix a `blocked` review from the UI (`POST /api/pr-reviews/{id}/fix`
with an optional prompt). The workflow first reads the PR from GitHub and declines, keeping the review
blocked with the reason, when it is merged (recorded instead), closed, changed since its review, or from a
fork Sentinel cannot push to. Otherwise the review becomes `fixing` and PR Review receives a `fix` command:
the reviewed head, its checks, the diff, the earlier attempts with their findings and failed checks, and the
operator's instruction. With the repository's `actions/fix.md` prompt and a `read_file` tool limited to the
checkout (refusing `.git`, paths outside it, files over `max_file_bytes`, and files with credential material),
it returns each changed file's complete content, a summary, and a commit subject. The worker applies the
changes to the checkout and runs the checks again on the fixed revision against the base.

The workflow's pure fix policy (`reviews/fix_policy.py`) declines a fix with no changes, a path outside the
repository, credential material, or a fixed revision that still fails a check; the review returns to
`blocked` with the reason, and the attempt keeps what was proposed. An accepted fix is saved on its attempt
and sent to sentinel-executor as `push-fix`: one commit that GitHub creates, authors, and signs as the
GitHub App on exactly the reviewed head, fast-forwarding the PR's own branch without force. The review becomes `acknowledged` at the pushed head, and the
next discovery reviews it once GitHub reports it clean, applying the same merge policy as any revision. A
failed agent run or push fails the review. Pushing to a Renovate branch makes Renovate stop rebasing it.

Sources: `sentinel/workflow/src/sentinel/workflow/reviews/`, `infra/chart/sentinel/config/common/repositories.yaml`,
`sentinel/pr-review/src/sentinel/agents/pr_review/run.py`,
`sentinel/pr-review/src/sentinel/agents/pr_review/policy.py`,
`sentinel/pr-review/src/sentinel/agents/pr_review/workspace.py`,
`sentinel/pr-review/src/sentinel/agents/pr_review/agent.py`, `sentinel/executor/src/sentinel/executor/git_workspace.py`,
`sentinel/executor/src/sentinel/executor/github.py`,
`infra/chart/sentinel/config/pr-review.yaml`, `infra/context/<repository>/prompts/pr-review/actions/`.
