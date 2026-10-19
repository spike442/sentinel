DROP TABLE IF EXISTS pr_reviews;

CREATE TABLE IF NOT EXISTS pr_reviews (
    entity_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    repository TEXT NOT NULL,
    owner TEXT NOT NULL,
    pull_request_number INTEGER NOT NULL,
    base_sha TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    pull_request_url TEXT NOT NULL,
    checks JSONB NOT NULL,
    risk TEXT,
    confidence TEXT,
    summary TEXT NOT NULL,
    findings JSONB NOT NULL,
    "merge" BOOLEAN,
    decision_reason TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    merge_commit_sha TEXT NOT NULL,
    timeline JSONB NOT NULL,
    attempts JSONB NOT NULL,
    tool_budget JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS pr_reviews_listing ON pr_reviews (updated_at DESC);
