DROP TABLE IF EXISTS incidents;

CREATE TABLE IF NOT EXISTS incidents (
    entity_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    repository TEXT NOT NULL,
    alert JSONB NOT NULL,
    diagnosis JSONB NOT NULL,
    pull_request_url TEXT,
    review_id TEXT,
    replayed_at TIMESTAMPTZ,
    manual_actions JSONB NOT NULL,
    timeline JSONB NOT NULL,
    attempts JSONB NOT NULL,
    tool_budget JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS incidents_listing ON incidents (updated_at DESC);
CREATE INDEX IF NOT EXISTS incidents_pull_request ON incidents (pull_request_url);
