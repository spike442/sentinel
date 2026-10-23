import type { Attempt, DomainRecord, TimelineEvent, ToolBudget } from "../../../model";

export type ProposedChange = { file_path: string; content: string; delete?: boolean };

export type CheckResult = { name: string; passed: boolean; output?: string };

export type ReviewAttemptResult = {
  checks?: CheckResult[];
  risk?: string;
  confidence?: string;
  summary?: string;
  findings?: string[];
  merge?: boolean;
  decision_reason?: string;
  commit_message?: string;
  changes?: ProposedChange[];
  commit_sha?: string;
  reason?: string;
  error?: string;
};

export type ReviewRecord = DomainRecord & {
  repository: string;
  owner?: string;
  pull_request_number: number;
  pull_request_url: string;
  base_sha?: string;
  head_sha?: string;
  checks?: CheckResult[];
  risk?: string | null;
  confidence?: string | null;
  summary: string;
  findings?: string[];
  merge?: boolean | null;
  decision_reason?: string;
  reviewed_at?: string | null;
  merged_at?: string | null;
  merge_commit_sha?: string;
  timeline?: TimelineEvent[];
  attempts?: Attempt<ReviewAttemptResult>[];
  tool_budget?: ToolBudget;
};
