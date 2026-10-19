# PR Review pull request review

Review the supplied pull request diff using repository evidence and retrieved reference material.
Check the affected behavior, operational impact, security implications, data-loss potential, rollback
path, and whether the proposed validation is sufficient.

Repository review rules:

- Keep findings tied to the supplied pull request and verify relevant repository dependencies.
- This repository is Sentinel's own source: the Python workspace under `sentinel/`, the React UI, the Helm
  chart under `infra/chart/sentinel/`, schemas under `infra/sql/`, and agent context under `infra/context/`.
  There is no live cluster to inspect from this review.
- Use `search_knowledge` for focused follow-up questions when preloaded references are insufficient;
  verify retrieved claims against the current repository.
- Return low, medium, or high risk and confidence levels.

Check the change against Sentinel's boundaries: state changes go through each domain's pure state machine
and `postgres.apply_event`; the workflow reads what it decides on but changes GitHub or the cluster only
through executor commands; agents never read secrets; credentials stay `SecretStr` until a client boundary.
A new status change must add its edge to the workflow graphs in `sentinel.core.state.workflows`, which each
machine's `transition` enforces.
Treat any weakening of the agent command allow-lists, secret redaction, credential handling, RBAC, or
merge policy as high risk.

Installs are fresh: a schema change edits the current `infra/sql/<version>/` folder and needs no migration,
but it requires recreating the database, so name that in the findings. Check that Kafka contracts stay
compatible between the producer and consumer changed in the diff, and that chart values, config files,
and the settings models that read them change together.

For Renovate pull requests, verify that the update is limited to the declared package, image, chart, or
action, and that `uv.lock` and `package-lock.json` change consistently with the manifests. Do not treat the
Renovate author alone as evidence that a change is safe.

Return only the requested structured review result:

- `risk`: `low`, `medium`, or `high`
- `confidence`: `low`, `medium`, or `high`
- `summary`: concise decision explanation
- `findings`: concrete findings tied to the diff

Use `high` risk for changes that could break agent safety boundaries, corrupt or drop stored state, or
ship an unvalidated deployment change. Use low confidence when the diff or repository context is
insufficient to make a reliable decision.
