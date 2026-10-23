import type { ReactNode } from "react";
import { formatTimestamp, sortByTimestamp } from "../format";
import type { Attempt, TimelineEvent } from "../model";
import { useStateTone } from "../tones";
import { humanize } from "../workflow";
import { AuditTrail, KeyValues, ToolBudgetPanel, budgetExhausted } from "./RecordSections";

export function shortSha(sha: string | undefined): string {
  return sha ? sha.slice(0, 12) : "";
}

export function Timeline({ events, label }: { events: TimelineEvent[]; label: string }) {
  const stateTone = useStateTone();
  const timeline = sortByTimestamp(events, true);
  if (!timeline.length) return <p className="section-empty">No timeline events recorded.</p>;
  return (
    <ol className="timeline" aria-label={label}>
      {timeline.map((entry, index) => {
        const facts = [entry.trigger && humanize(entry.trigger), shortSha(entry.head_sha ?? entry.sha)].filter(Boolean);
        return (
          <li key={`${entry.at}-${index}`}>
            <span className={`state-dot tone-${stateTone(entry.event)}`} aria-hidden="true" />
            <strong>{humanize(entry.event)}</strong>
            <time>{formatTimestamp(entry.at)}</time>
            {facts.length > 0 && <p className="timeline-facts">{facts.join(" · ")}</p>}
            {entry.prompt && <p>“{entry.prompt}”</p>}
            {entry.reason && <p>{entry.reason}</p>}
          </li>
        );
      })}
    </ol>
  );
}

function AttemptCard({ attempt, open, children }: { attempt: Attempt<unknown>; open: boolean; children: ReactNode }) {
  const stateTone = useStateTone();
  const actions = attempt.audit_actions ?? [];
  const revision = shortSha(attempt.head_sha);
  return (
    <details className={`nested attempt ${attempt.status === "failed" ? "flagged" : ""}`} open={open}>
      <summary>
        <span className={`state-dot tone-${stateTone(attempt.status)}`} aria-hidden="true" />
        <span className="attempt-number">#{attempt.number}</span>
        <span className="attempt-trigger">{humanize(attempt.trigger)}</span>
        <span className="attempt-status">{humanize(attempt.status)}</span>
        <time>{formatTimestamp(attempt.started_at)}</time>
      </summary>
      {attempt.prompt && <p className="attempt-prompt">“{attempt.prompt}”</p>}
      <KeyValues
        values={{
          revision,
          started: formatTimestamp(attempt.started_at),
          finished: attempt.finished_at ? formatTimestamp(attempt.finished_at) : undefined,
          workflow: attempt.workflow_id,
        }}
      />
      {children}
      {budgetExhausted(attempt.tool_budget) && <ToolBudgetPanel budget={attempt.tool_budget} />}
      {actions.length > 0 && (
        <details className="nested">
          <summary>Audit trail · {actions.length}</summary>
          <AuditTrail actions={actions} />
        </details>
      )}
    </details>
  );
}

export function AttemptHistory<Result>({
  attempts,
  renderResult,
}: {
  attempts: Attempt<Result>[];
  renderResult: (result: Result) => ReactNode;
}) {
  if (!attempts.length) return <p className="section-empty">No attempts yet.</p>;
  const newestFirst = [...attempts].reverse();
  return (
    <div className="attempts">
      {newestFirst.map((attempt, index) => (
        <AttemptCard attempt={attempt} open={index === 0} key={attempt.number}>
          {renderResult(attempt.result)}
        </AttemptCard>
      ))}
    </div>
  );
}
