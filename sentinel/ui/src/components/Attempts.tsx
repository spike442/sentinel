import type { ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import { formatTimestamp, sortByTimestamp } from "../format";
import type { Attempt, AttemptResult, CheckResult, TimelineEvent } from "../model";
import { humanize, stateTone } from "../workflow";
import { AuditTrail, Block, DiagnosisView, KeyValues, TextList, ToolBudgetPanel, budgetExhausted } from "./RecordSections";

function shortSha(sha: string | undefined): string {
  return sha ? sha.slice(0, 12) : "";
}

export function Timeline({ events, label }: { events: TimelineEvent[]; label: string }) {
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

export function ChecksList({ checks }: { checks: CheckResult[] | undefined }) {
  if (!checks?.length) return <p className="section-empty">No checks recorded.</p>;
  return (
    <>
      {checks.map((check, index) => (
        <details className={`nested ${check.passed ? "" : "flagged"}`} key={`${check.name}-${index}`}>
          <summary>
            <span className={`state-dot tone-${check.passed ? "done" : "failed"}`} aria-hidden="true" /> {check.name} ·{" "}
            {check.passed ? "passed" : "failed"}
          </summary>
          <Block value={check.output || "No output."} />
        </details>
      ))}
    </>
  );
}

export function ReviewAttemptResult({ result }: { result: AttemptResult }) {
  const fix = result.changes !== undefined || result.commit_sha !== undefined;
  return (
    <>
      {result.error && <p className="audit-error">{result.error}</p>}
      {result.reason && <p className="attempt-reason">Fix declined: {result.reason}</p>}
      {result.decision_reason && (
        <>
          <h4>Decision</h4>
          <p>{result.decision_reason}</p>
        </>
      )}
      {result.summary && (
        <>
          <h4>{fix ? "Fix" : "Summary"}</h4>
          <p>{result.summary}</p>
        </>
      )}
      {result.risk && (
        <KeyValues values={{ risk: result.risk, confidence: result.confidence, merge: result.merge === undefined ? undefined : String(result.merge) }} />
      )}
      {Boolean(result.findings?.length) && (
        <>
          <h4>Findings</h4>
          <TextList items={result.findings} />
        </>
      )}
      {result.commit_message && <KeyValues values={{ commit: result.commit_message, pushed: shortSha(result.commit_sha) }} />}
      {!result.commit_message && result.commit_sha && <KeyValues values={{ pushed: shortSha(result.commit_sha) }} />}
      {Boolean(result.changes?.length) && (
        <>
          <h4>Changed files</h4>
          {result.changes?.map((change) => (
            <details className="nested" key={change.file_path}>
              <summary>{change.file_path}</summary>
              <Block value={change.content} />
            </details>
          ))}
        </>
      )}
      {Boolean(result.checks?.length) && (
        <>
          <h4>{fix ? "Checks of the fixed revision" : "Checks"}</h4>
          <ChecksList checks={result.checks} />
        </>
      )}
    </>
  );
}

export function IncidentAttemptResult({ result }: { result: AttemptResult }) {
  return (
    <>
      {result.error && <p className="audit-error">{result.error}</p>}
      {result.diagnosis && <DiagnosisView diagnosis={result.diagnosis} />}
      {result.pull_request_url && (
        <a className="action-button" href={result.pull_request_url} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Pull request
        </a>
      )}
    </>
  );
}

function AttemptCard({ attempt, open, children }: { attempt: Attempt; open: boolean; children: ReactNode }) {
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

export function AttemptHistory({
  attempts,
  renderResult,
}: {
  attempts: Attempt[];
  renderResult: (result: AttemptResult) => ReactNode;
}) {
  if (!attempts.length) return <p className="section-empty">No attempts yet.</p>;
  const newestFirst = [...attempts].reverse();
  return (
    <div className="attempts">
      {newestFirst.map((attempt, index) => (
        <AttemptCard attempt={attempt} open={index === 0} key={attempt.number}>
          {renderResult(attempt.result ?? {})}
        </AttemptCard>
      ))}
    </div>
  );
}
