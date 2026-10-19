import type { ReactNode } from "react";
import { Gauge } from "lucide-react";
import { formatTimestamp } from "../format";
import type { AuditAction, Diagnosis, ToolBudget } from "../model";
import { humanize } from "../workflow";
import { ManualActionCard } from "./ManualActions";

export function Section({
  title,
  count,
  open = false,
  children,
}: {
  title: string;
  count?: number;
  open?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="detail-section" open={open}>
      <summary>
        <span>{title}</span>
        {count !== undefined && <span className="section-count">{count}</span>}
      </summary>
      <div className="detail-section-body">{children}</div>
    </details>
  );
}

export function KeyValues({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!entries.length) return <p className="section-empty">Nothing recorded.</p>;
  return (
    <dl className="key-values">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TextList({ items, empty = "Nothing recorded." }: { items: string[] | undefined; empty?: string }) {
  if (!items?.length) return <p className="section-empty">{empty}</p>;
  return (
    <ul className="text-list">
      {items.map((item, index) => (
        <li key={`${index}-${item.slice(0, 24)}`}>{item}</li>
      ))}
    </ul>
  );
}

export function Block({ value }: { value: unknown }) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="data-block">
      <code>{text}</code>
    </pre>
  );
}

export function budgetExhausted(budget: ToolBudget | undefined): boolean {
  return Boolean(budget?.exhausted_tools?.length);
}

export function BudgetChip({ budget }: { budget: ToolBudget | undefined }) {
  if (!budgetExhausted(budget)) return null;
  return (
    <span className="state-chip tone-waiting budget-chip" title={`Refused calls to ${budget?.exhausted_tools?.join(", ")}`}>
      <Gauge size={12} /> Tool budget reached
    </span>
  );
}

export function ToolBudgetPanel({ budget }: { budget: ToolBudget | undefined }) {
  const limit = budget?.limit ?? 0;
  if (!limit) return <p className="section-empty">No agent run has reported its tool budget yet.</p>;
  const exhausted = new Set(budget?.exhausted_tools ?? []);
  const calls = Object.entries(budget?.calls ?? {});
  return (
    <>
      {exhausted.size > 0 && (
        <p className="budget-warning">
          The last run reached its limit of {limit} calls for {[...exhausted].join(", ")}; the agent answered with the evidence it had
          gathered and further calls were refused.
        </p>
      )}
      <ul className="budget-list">
        {calls.map(([tool, used]) => (
          <li key={tool} className={exhausted.has(tool) ? "exhausted" : ""}>
            <span className="budget-tool">{tool}</span>
            <span className="budget-bar" aria-hidden="true">
              <span style={{ width: `${Math.min(100, (used / limit) * 100)}%` }} />
            </span>
            <span className="budget-count">
              {used}/{limit}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function DiagnosisView({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <div className="diagnosis">
      {diagnosis.hypothesis && <p className="diagnosis-hypothesis">{diagnosis.hypothesis}</p>}
      <KeyValues
        values={{
          status: diagnosis.status,
          incident: diagnosis.incident,
          risk: diagnosis.risk,
          confidence: diagnosis.confidence,
        }}
      />
      <h4>Evidence</h4>
      <TextList items={diagnosis.evidence} />
      <h4>Validation</h4>
      <TextList items={diagnosis.validation} />
      {diagnosis.rollback && (
        <>
          <h4>Rollback</h4>
          <p>{diagnosis.rollback}</p>
        </>
      )}
      {Boolean(diagnosis.proposed_files?.length) && (
        <>
          <h4>Proposed files</h4>
          <TextList items={diagnosis.proposed_files} />
        </>
      )}
      {(diagnosis.pr_title || diagnosis.pr_body) && (
        <>
          <h4>Pull request</h4>
          {diagnosis.pr_title && <p className="diagnosis-pr-title">{diagnosis.pr_title}</p>}
          {diagnosis.pr_body && <Block value={diagnosis.pr_body} />}
        </>
      )}
      {diagnosis.proposed_changes?.map((change) => (
        <details className="nested" key={change.file_path}>
          <summary>{change.file_path}</summary>
          <Block value={change.content} />
        </details>
      ))}
      {Boolean(diagnosis.manual_actions?.length) && (
        <>
          <h4>Manual actions</h4>
          {diagnosis.manual_actions?.map((action, index) => (
            <ManualActionCard action={action} key={`${action.command}-${index}`} />
          ))}
        </>
      )}
    </div>
  );
}

type Usage = { input_tokens?: number; output_tokens?: number; total_tokens?: number };

function auditStatus(details: Record<string, unknown>): string {
  return typeof details.status === "string" ? details.status : "";
}

function auditLabel(entry: AuditAction): string {
  const tool = entry.details.tool;
  return typeof tool === "string" ? `${humanize(entry.action)} · ${tool}` : humanize(entry.action);
}

function AuditBody({ entry }: { entry: AuditAction }) {
  const { details } = entry;
  if (entry.action === "tool_call") {
    return (
      <>
        <h4>Arguments</h4>
        <Block value={details.arguments ?? {}} />
        {details.output !== undefined && (
          <>
            <h4>Output</h4>
            <Block value={details.output} />
          </>
        )}
        {details.error !== undefined && <p className="audit-error">{String(details.error)}</p>}
      </>
    );
  }
  if (entry.action === "llm_response") {
    const usage = (details.usage ?? {}) as Usage;
    return (
      <KeyValues
        values={{
          response: details.response_id,
          input_tokens: usage.input_tokens,
          output_tokens: usage.output_tokens,
          total_tokens: usage.total_tokens,
          error: details.error,
        }}
      />
    );
  }
  return <Block value={details} />;
}

export function AuditTrail({ actions }: { actions: AuditAction[] }) {
  if (!actions.length) return <p className="section-empty">No audit actions recorded.</p>;
  const toolCalls = actions.filter((entry) => entry.action === "tool_call").length;
  const tokens = actions.reduce((total, entry) => total + (((entry.details.usage ?? {}) as Usage).total_tokens ?? 0), 0);
  return (
    <>
      <p className="audit-summary">
        {actions.length} actions · {toolCalls} tool calls · {tokens.toLocaleString()} tokens
      </p>
      <ol className="audit-trail">
        {actions.map((entry, index) => {
          const status = auditStatus(entry.details);
          const flagged = status === "failed" || status === "error" || entry.action === "tool_budget_exhausted" || entry.action === "workflow_failed";
          return (
            <li key={`${entry.timestamp}-${index}`}>
              <details className={`nested audit-entry ${flagged ? "flagged" : ""}`}>
                <summary>
                  <span className="audit-index">{index + 1}</span>
                  <span className="audit-label">{auditLabel(entry)}</span>
                  {status && <span className="audit-status">{status}</span>}
                  <time>{formatTimestamp(entry.timestamp)}</time>
                </summary>
                <AuditBody entry={entry} />
              </details>
            </li>
          );
        })}
      </ol>
    </>
  );
}
