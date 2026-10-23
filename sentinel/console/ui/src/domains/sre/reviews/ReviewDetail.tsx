import { ExternalLink } from "lucide-react";
import { AttemptHistory, Timeline, shortSha } from "../../../components/Attempts";
import { Block, KeyValues, Section, TextList, ToolBudgetPanel, budgetExhausted } from "../../../components/RecordSections";
import { formatTimestamp } from "../../../format";
import type { DetailProps } from "../../types";
import type { CheckResult, ReviewAttemptResult, ReviewRecord } from "./model";

function ChecksList({ checks }: { checks: CheckResult[] | undefined }) {
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

function ReviewAttempt({ result }: { result: ReviewAttemptResult }) {
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
              <summary>{change.delete ? `${change.file_path} (deleted)` : change.file_path}</summary>
              {!change.delete && <Block value={change.content} />}
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

export default function ReviewDetail({ record, actions }: DetailProps) {
  const review = record as ReviewRecord;
  const checks = review.checks ?? [];
  const timeline = review.timeline ?? [];
  const attempts = review.attempts ?? [];
  const decision = review.merge === null || review.merge === undefined ? "—" : review.merge ? "merge" : "hold";
  return (
    <>
      <p className="detail-summary">{review.summary || "No review summary recorded yet."}</p>
      <dl className="detail-facts">
        <div><dt>Risk · confidence</dt><dd>{review.risk ?? "—"} · {review.confidence ?? "—"}</dd></div>
        <div><dt>Decision</dt><dd>{decision}</dd></div>
        <div><dt>Checks</dt><dd>{checks.length ? `${checks.filter((check) => check.passed).length}/${checks.length} passed` : "—"}</dd></div>
        <div><dt>Attempts</dt><dd>{attempts.length || "—"}</dd></div>
        <div><dt>Head</dt><dd><code>{review.head_sha?.slice(0, 12) ?? "—"}</code></dd></div>
        <div><dt>Reviewed</dt><dd>{formatTimestamp(review.reviewed_at)}</dd></div>
        <div><dt>Updated</dt><dd>{formatTimestamp(review.updated_at)}</dd></div>
        {review.merged_at && <div><dt>Merged</dt><dd>{formatTimestamp(review.merged_at)}</dd></div>}
        {review.merge_commit_sha && <div><dt>Merge commit</dt><dd><code>{review.merge_commit_sha.slice(0, 12)}</code></dd></div>}
      </dl>
      <div className="detail-actions">
        <a className="action-button" href={review.pull_request_url} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Pull request
        </a>
        {actions}
      </div>
      <Section title="Decision" open>
        {review.decision_reason ? <p>{review.decision_reason}</p> : <p className="section-empty">No merge decision recorded yet.</p>}
      </Section>
      <Section title="Findings" count={review.findings?.length ?? 0} open>
        <TextList items={review.findings} empty="No findings recorded." />
      </Section>
      <Section title="Tool budget" open={budgetExhausted(review.tool_budget)}>
        <ToolBudgetPanel budget={review.tool_budget} />
      </Section>
      <Section title="Checks" count={checks.length}>
        <ChecksList checks={checks} />
      </Section>
      <Section title="Timeline" count={timeline.length} open>
        <Timeline events={timeline} label="Review timeline" />
      </Section>
      <Section title="Attempts" count={attempts.length} open>
        <AttemptHistory attempts={attempts} renderResult={(result) => <ReviewAttempt result={result} />} />
      </Section>
      <Section title="Record">
        <KeyValues
          values={{
            id: review.id,
            workflow: review.workflow_id,
            owner: review.owner,
            base: review.base_sha,
            head: review.head_sha,
            merge_commit: review.merge_commit_sha,
          }}
        />
      </Section>
    </>
  );
}
