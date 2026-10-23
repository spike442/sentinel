export type DomainConfig = { id: string; api: string; icon?: string };

export type DomainKind = "workflow" | "data";

export type WorkflowSummary = { id: string; label: string; agent: string; running: boolean; active: number };

export type DomainManifest = {
  id: string;
  label: string;
  icon: string;
  kind: DomainKind;
  version: string;
  enabled: boolean;
  running: boolean;
  active: number;
  workflows?: WorkflowSummary[];
};

export type StateTone = "active" | "waiting" | "done" | "failed" | "closed";

export type RecordAction = {
  name: string;
  label: string;
  tone: string;
  prompt: { message: string; required: boolean } | null;
  confirm: string | null;
};

export type RecordLink = { domain: string; workflow: string; record_id: string; label: string };

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

export type TimelineEvent = {
  at: string;
  event: string;
  prompt?: string;
  reason?: string;
  trigger?: string;
  head_sha?: string;
  sha?: string;
};

export type Attempt<Result = Record<string, unknown>> = {
  number: number;
  trigger: string;
  workflow_id: string;
  prompt: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  base_sha?: string;
  head_sha?: string;
  result: Result;
  audit_actions: AuditAction[];
  tool_budget: ToolBudget;
};

export type DomainRecord = {
  id: string;
  status: string;
  title: string;
  updated_at: string;
  workflow_id?: string | null;
  actions: RecordAction[];
  links?: RecordLink[];
  timeline?: TimelineEvent[];
  attempts?: Attempt[];
  tool_budget?: ToolBudget;
};

export type WorkflowTransition = {
  source: string | null;
  event: string;
  target: string;
};

export type WorkflowView = {
  domain: string;
  states: { name: string; tone: StateTone }[];
  transitions: WorkflowTransition[];
  tones: Record<string, StateTone>;
};

export type WorkflowGraph = {
  domain: string;
  states: string[];
  transitions: WorkflowTransition[];
  tones: Record<string, StateTone>;
};

export type DatasetSummary = { name: string; label: string; trade_dated: boolean };

export type DatasetRows = {
  name: string;
  label: string;
  trade_date: string | null;
  columns: string[];
  rows: Record<string, unknown>[];
};
