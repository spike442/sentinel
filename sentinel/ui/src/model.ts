export const INCIDENT_STATUS = {
  ACKNOWLEDGED: "acknowledged",
  REOPENED: "reopened",
  RUNNING: "running",
  AWAITING: "awaiting",
  BLOCKED: "blocked",
  FAILED: "failed",
  IGNORED: "ignored",
  RESOLVED: "resolved",
  SKIPPED: "skipped",
} as const;
type IncidentStatus =
  (typeof INCIDENT_STATUS)[keyof typeof INCIDENT_STATUS];

const PR_REVIEW_STATUS = {
  ACKNOWLEDGED: "acknowledged",
  RUNNING: "running",
  BLOCKED: "blocked",
  FIXING: "fixing",
  FAILED: "failed",
  MERGED: "merged",
} as const;
type PrReviewStatus = (typeof PR_REVIEW_STATUS)[keyof typeof PR_REVIEW_STATUS];

const REPLAYABLE_INCIDENT_STATUSES = new Set<IncidentStatus>([
  INCIDENT_STATUS.ACKNOWLEDGED,
  INCIDENT_STATUS.REOPENED,
  INCIDENT_STATUS.RUNNING,
  INCIDENT_STATUS.AWAITING,
  INCIDENT_STATUS.BLOCKED,
  INCIDENT_STATUS.FAILED,
  INCIDENT_STATUS.SKIPPED,
]);
const CLOSED_INCIDENT_STATUSES = new Set<IncidentStatus>([
  INCIDENT_STATUS.IGNORED,
  INCIDENT_STATUS.RESOLVED,
]);
export const REPLAYABLE_REVIEW_STATUSES = new Set<PrReviewStatus>([
  PR_REVIEW_STATUS.BLOCKED,
  PR_REVIEW_STATUS.FAILED,
  PR_REVIEW_STATUS.RUNNING,
  PR_REVIEW_STATUS.FIXING,
]);
export const FIXABLE_REVIEW_STATUSES = new Set<PrReviewStatus>([PR_REVIEW_STATUS.BLOCKED]);

export type ManualAction = {
  title: string;
  command: string;
  reason: string;
  validation: string;
};
export type ManualActionRun = Partial<ManualAction> & {
  action_index?: number;
  approval_id?: string;
  workflow_id?: string;
  status?: string;
  at?: string;
  claim_at?: string;
  exit_code?: number | null;
  stdout?: string;
  stderr?: string;
  error?: string | null;
};
export type AuditAction = {
  action: string;
  details: Record<string, unknown>;
  timestamp: string;
};
export type ToolBudget = {
  limit?: number;
  calls?: Record<string, number>;
  exhausted_tools?: string[];
};
type ProposedChange = { file_path: string; content: string; delete?: boolean };
export type CheckResult = { name: string; passed: boolean; output?: string };
export type Diagnosis = {
  status?: string;
  incident?: string;
  hypothesis?: string;
  confidence?: "low" | "medium" | "high";
  risk?: "low" | "medium" | "high" | "critical";
  evidence?: string[];
  proposed_files?: string[];
  validation?: string[];
  rollback?: string;
  pr_title?: string;
  pr_body?: string;
  proposed_changes?: ProposedChange[];
  manual_actions?: ManualAction[];
};
export type TimelineEvent = {
  at: string;
  event: string;
  prompt?: string;
  reason?: string;
  trigger?: string;
  head_sha?: string;
  sha?: string;
};
export type AttemptResult = {
  diagnosis?: Diagnosis;
  pull_request_url?: string | null;
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
export type Attempt = {
  number: number;
  trigger: string;
  workflow_id: string;
  prompt: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  base_sha?: string;
  head_sha?: string;
  result: AttemptResult;
  audit_actions: AuditAction[];
  tool_budget: ToolBudget;
};
export const DOMAINS = ["sre", "pr-review"] as const;
export type Domain = (typeof DOMAINS)[number];
export type ManagedAgent = {
  domain: Domain;
  enabled: boolean;
  running: boolean;
};
type IncidentAction = "open-pr" | "replay" | "ignore" | "delete";
export type PullRequestReview = {
  id: string;
  workflow_id?: string | null;
  repository: string;
  owner?: string;
  pull_request_number: number;
  pull_request_url: string;
  base_sha?: string;
  head_sha?: string;
  status: PrReviewStatus;
  checks?: CheckResult[];
  risk?: string | null;
  confidence?: string | null;
  summary: string;
  findings?: string[];
  merge?: boolean | null;
  decision_reason?: string;
  reviewed_at?: string | null;
  updated_at: string;
  merged_at?: string | null;
  merge_commit_sha?: string;
  timeline?: TimelineEvent[];
  attempts?: Attempt[];
  tool_budget?: ToolBudget;
};
export type Incident = {
  id: string;
  workflowId: string;
  repository: string;
  title: string;
  summary: string;
  source: string;
  alertname: string;
  alertStatus: string;
  startsAt: string;
  endsAt: string;
  fingerprint: string;
  generatorUrl: string;
  alertLabels: Record<string, string>;
  alertAnnotations: Record<string, string>;
  pullRequestUrl: string;
  status: IncidentStatus;
  severity: string;
  namespace: string;
  pod: string;
  confidence: "low" | "medium" | "high";
  risk: "low" | "medium" | "high" | "critical";
  updated: string;
  replayedAt: string | null;
  diagnosis: Diagnosis;
  manualActions: ManualAction[];
  manualActionHistory: ManualActionRun[];
  timeline: TimelineEvent[];
  attempts: Attempt[];
  toolBudget: ToolBudget;
  actions: IncidentAction[];
};

export type ApiIncident = {
  id: string;
  workflow_id?: string | null;
  repository?: string;
  status: IncidentStatus;
  source?: string;
  alert: {
    source?: string;
    status?: string;
    startsAt?: string;
    endsAt?: string;
    fingerprint?: string;
    generatorURL?: string;
    labels?: Record<string, string>;
    annotations?: Record<string, string>;
  };
  diagnosis: Diagnosis;
  pull_request_url?: string | null;
  updated_at?: string;
  replayed_at?: string | null;
  manual_actions?: ManualActionRun[];
  timeline?: TimelineEvent[];
  attempts?: Attempt[];
  tool_budget?: ToolBudget;
};

export function toIncident(item: ApiIncident): Incident {
  const annotations = item.alert.annotations ?? {};
  return {
    id: item.id,
    workflowId: item.workflow_id ?? "",
    repository: item.repository ?? "",
    title: annotations.summary ?? item.diagnosis.incident ?? item.id,
    summary: annotations.description ?? "No incident description recorded.",
    source: item.source ?? item.alert.source ?? item.alert.labels?.source ?? "unknown",
    alertname: item.alert.labels?.alertname ?? "unknown",
    alertStatus: item.alert.status ?? "unknown",
    startsAt: item.alert.startsAt ?? "unknown",
    endsAt: item.alert.endsAt ?? "",
    fingerprint: item.alert.fingerprint ?? "",
    generatorUrl: item.alert.generatorURL ?? "",
    alertLabels: item.alert.labels ?? {},
    alertAnnotations: annotations,
    pullRequestUrl: item.pull_request_url ?? "",
    status: item.status,
    severity: item.alert.labels?.severity ?? "unknown",
    namespace: item.alert.labels?.namespace ?? "",
    pod: item.alert.labels?.pod ?? "",
    confidence: item.diagnosis.confidence ?? "low",
    risk: item.diagnosis.risk ?? "low",
    updated: item.updated_at ?? "",
    replayedAt: item.replayed_at ?? null,
    diagnosis: item.diagnosis,
    manualActions: item.diagnosis.manual_actions ?? [],
    manualActionHistory: item.manual_actions ?? [],
    timeline: item.timeline ?? [],
    attempts: item.attempts ?? [],
    toolBudget: item.tool_budget ?? {},
    actions: [
      ...(item.pull_request_url ? (["open-pr"] as const) : []),
      ...(REPLAYABLE_INCIDENT_STATUSES.has(item.status) ? (["replay"] as const) : []),
      ...(CLOSED_INCIDENT_STATUSES.has(item.status) ? [] : (["ignore"] as const)),
      "delete",
    ],
  };
}

export type WorkflowTransition = {
  source: string | null;
  event: string;
  target: string;
};
export type WorkflowGraph = {
  domain: Domain;
  states: string[];
  transitions: WorkflowTransition[];
};
