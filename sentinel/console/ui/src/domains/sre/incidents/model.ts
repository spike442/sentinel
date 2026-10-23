import type { Attempt, DomainRecord, TimelineEvent, ToolBudget } from "../../../model";

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

export type ProposedChange = { file_path: string; content: string; delete?: boolean };

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

export type IncidentAttemptResult = {
  diagnosis?: Diagnosis;
  pull_request_url?: string | null;
  error?: string;
};

export type IncidentRecord = DomainRecord & {
  repository?: string;
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
  replayed_at?: string | null;
  manual_actions?: ManualActionRun[];
  timeline?: TimelineEvent[];
  attempts?: Attempt<IncidentAttemptResult>[];
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
  status: string;
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
  attempts: Attempt<IncidentAttemptResult>[];
  toolBudget: ToolBudget;
};

export function toIncident(item: IncidentRecord): Incident {
  const annotations = item.alert.annotations ?? {};
  return {
    id: item.id,
    workflowId: item.workflow_id ?? "",
    repository: item.repository ?? "",
    title: item.title,
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
    updated: item.updated_at,
    replayedAt: item.replayed_at ?? null,
    diagnosis: item.diagnosis,
    manualActions: item.diagnosis.manual_actions ?? [],
    manualActionHistory: item.manual_actions ?? [],
    timeline: item.timeline ?? [],
    attempts: item.attempts ?? [],
    toolBudget: item.tool_budget ?? {},
  };
}
