import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ExternalLink, Wrench } from "lucide-react";
import { deleteIncident, ignoreIncident, replayIncident } from "../api/incidents";
import { deleteReview, fixReview, replayReview } from "../api/reviews";
import { formatTimestamp, sortByTimestamp } from "../format";
import { NARROW_SCREEN } from "../hooks/useMediaQuery";
import {
  FIXABLE_REVIEW_STATUSES,
  INCIDENT_STATUS,
  REPLAYABLE_REVIEW_STATUSES,
  type Incident,
  type PullRequestReview,
  type TimelineEvent,
} from "../model";
import { humanize, stateTone } from "../workflow";
import { AttemptHistory, ChecksList, IncidentAttemptResult, ReviewAttemptResult, Timeline } from "./Attempts";
import { ManualActions } from "./ManualActions";
import {
  BudgetChip,
  DiagnosisView,
  KeyValues,
  Section,
  TextList,
  ToolBudgetPanel,
  budgetExhausted,
} from "./RecordSections";

export type DomainRecord =
  | { kind: "incident"; id: string; status: string; title: string; updated: string; incident: Incident }
  | { kind: "review"; id: string; status: string; title: string; updated: string; review: PullRequestReview };

export function incidentRecord(incident: Incident): DomainRecord {
  return { kind: "incident", id: incident.id, status: incident.status, title: incident.title, updated: incident.updated, incident };
}

export function reviewRecord(review: PullRequestReview): DomainRecord {
  const title = `${review.repository} #${review.pull_request_number}`;
  return { kind: "review", id: review.id, status: review.status, title, updated: review.updated_at, review };
}

const NON_STATUS_EVENTS = new Set(["manual_action_executed", "replayed", "fix_declined"]);

export function visitedStates(record: DomainRecord | null): string[] {
  if (!record) return [];
  const events: TimelineEvent[] = record.kind === "incident" ? record.incident.timeline : (record.review.timeline ?? []);
  const timeline = sortByTimestamp(events);
  const states = timeline.map((entry) => entry.event).filter((event) => !NON_STATUS_EVENTS.has(event));
  return [...states, record.status];
}

export function RecordList({
  records,
  selectedId,
  onSelect,
}: {
  records: DomainRecord[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (!records.length) return <p className="empty">No records in this state.</p>;
  return (
    <ul className="record-list">
      {records.map((record) => (
        <li key={record.id}>
          <button className={`record-row ${selectedId === record.id ? "selected" : ""}`} onClick={() => onSelect(record.id)}>
            <span className={`state-dot tone-${stateTone(record.status)}`} aria-hidden="true" />
            <span className="record-title">{record.title}</span>
            <span className="record-state">{humanize(record.status)}</span>
            <time className="record-time">{formatTimestamp(record.updated)}</time>
          </button>
        </li>
      ))}
    </ul>
  );
}

function useAction(onDone: () => void, onError: (message: string) => void) {
  const [busy, setBusy] = useState(false);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
      onDone();
    } catch (error) {
      onError(error instanceof Error ? error.message : "The action failed.");
    } finally {
      setBusy(false);
    }
  }
  return { busy, run };
}

function replayPrompt(incident: Incident): string | null {
  if (incident.status !== INCIDENT_STATUS.BLOCKED) return "";
  const prompt = window.prompt("Tell the agent what to reconsider before replaying this blocked incident") ?? "";
  return prompt.trim() ? prompt : null;
}

function operatorPrompt(message: string): string | null {
  const prompt = window.prompt(message);
  return prompt === null ? null : prompt.trim();
}

function IncidentDetail({ incident, onRefresh, onError }: DetailProps & { incident: Incident }) {
  const { busy, run } = useAction(onRefresh, onError);
  const replay = () => {
    const prompt = replayPrompt(incident);
    if (prompt !== null) void run(() => replayIncident(incident, prompt));
  };
  return (
    <>
      <header className="detail-header">
        <h3>{incident.title}</h3>
        <div className="detail-chips">
          <BudgetChip budget={incident.toolBudget} />
          <span className={`state-chip tone-${stateTone(incident.status)}`}>{humanize(incident.status)}</span>
        </div>
      </header>
      <p className="detail-summary">{incident.summary}</p>
      <dl className="detail-facts">
        <div><dt>Alert</dt><dd>{incident.alertname}</dd></div>
        <div><dt>Alert status</dt><dd>{incident.alertStatus}</dd></div>
        <div><dt>Severity</dt><dd>{incident.severity}</dd></div>
        <div><dt>Namespace</dt><dd>{incident.namespace || "—"}</dd></div>
        <div><dt>Pod</dt><dd>{incident.pod || "—"}</dd></div>
        <div><dt>Repository</dt><dd>{incident.repository || "—"}</dd></div>
        <div><dt>Source</dt><dd>{incident.source}</dd></div>
        <div><dt>Risk · confidence</dt><dd>{incident.risk} · {incident.confidence}</dd></div>
        <div><dt>Started</dt><dd>{formatTimestamp(incident.startsAt)}</dd></div>
        <div><dt>Updated</dt><dd>{formatTimestamp(incident.updated)}</dd></div>
        {incident.replayedAt && <div><dt>Replayed</dt><dd>{formatTimestamp(incident.replayedAt)}</dd></div>}
      </dl>
      <div className="detail-actions">
        {incident.pullRequestUrl && (
          <a className="action-button" href={incident.pullRequestUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> Pull request
          </a>
        )}
        {incident.actions.includes("replay") && (
          <button className="action-button" disabled={busy} onClick={replay}>Replay</button>
        )}
        {incident.actions.includes("ignore") && (
          <button className="action-button" disabled={busy} onClick={() => void run(() => ignoreIncident(incident))}>Ignore</button>
        )}
        {incident.actions.includes("delete") && (
          <button
            className="action-button danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm("Delete this incident and its history?")) void run(() => deleteIncident(incident));
            }}
          >
            Delete
          </button>
        )}
      </div>
      <ManualActions incident={incident} onRefresh={onRefresh} onError={onError} />
      <Section title="Diagnosis" open>
        <DiagnosisView diagnosis={incident.diagnosis} />
      </Section>
      <Section title="Tool budget" open={budgetExhausted(incident.toolBudget)}>
        <ToolBudgetPanel budget={incident.toolBudget} />
      </Section>
      <Section title="Timeline" count={incident.timeline.length} open>
        <Timeline events={incident.timeline} label="Incident timeline" />
      </Section>
      <Section title="Attempts" count={incident.attempts.length} open>
        <AttemptHistory attempts={incident.attempts} renderResult={(result) => <IncidentAttemptResult result={result} />} />
      </Section>
      <Section title="Alert">
        <h4>Labels</h4>
        <KeyValues values={incident.alertLabels} />
        <h4>Annotations</h4>
        <KeyValues values={incident.alertAnnotations} />
        <h4>Alert record</h4>
        <KeyValues
          values={{
            fingerprint: incident.fingerprint,
            starts: incident.startsAt,
            ends: incident.endsAt,
          }}
        />
        {incident.generatorUrl && (
          <a className="action-button" href={incident.generatorUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> Source query
          </a>
        )}
      </Section>
      <Section title="Record">
        <KeyValues values={{ id: incident.id, workflow: incident.workflowId, updated: formatTimestamp(incident.updated) }} />
      </Section>
    </>
  );
}

function ReviewDetail({ review, onRefresh, onError }: DetailProps & { review: PullRequestReview }) {
  const { busy, run } = useAction(onRefresh, onError);
  const checks = review.checks ?? [];
  const timeline = review.timeline ?? [];
  const attempts = review.attempts ?? [];
  const replay = () => {
    const prompt = operatorPrompt("Replay this review. Optionally tell the reviewer what to reconsider.");
    if (prompt !== null) void run(() => replayReview(review, prompt));
  };
  const fix = () => {
    const prompt = operatorPrompt("Fix it: the reviewer fixes what blocked this PR and pushes a commit to its branch. Optionally tell it what to fix.");
    if (prompt !== null) void run(() => fixReview(review, prompt));
  };
  const decision = review.merge === null || review.merge === undefined ? "—" : review.merge ? "merge" : "hold";
  return (
    <>
      <header className="detail-header">
        <h3>{review.repository} #{review.pull_request_number}</h3>
        <div className="detail-chips">
          <BudgetChip budget={review.tool_budget} />
          <span className={`state-chip tone-${stateTone(review.status)}`}>{humanize(review.status)}</span>
        </div>
      </header>
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
        {FIXABLE_REVIEW_STATUSES.has(review.status) && (
          <button className="action-button primary" disabled={busy} onClick={fix}>
            <Wrench size={14} /> Fix it
          </button>
        )}
        {REPLAYABLE_REVIEW_STATUSES.has(review.status) && (
          <button className="action-button" disabled={busy} onClick={replay}>Replay</button>
        )}
        <button
          className="action-button danger"
          disabled={busy}
          onClick={() => {
            if (window.confirm("Delete this review record?")) void run(() => deleteReview(review));
          }}
        >
          Delete
        </button>
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
        <AttemptHistory attempts={attempts} renderResult={(result) => <ReviewAttemptResult result={result} />} />
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

type DetailProps = { onRefresh: () => void; onError: (message: string) => void };

export function RecordDetail({
  record,
  onBack,
  ...props
}: DetailProps & { record: DomainRecord | null; onBack: () => void }) {
  const article = useRef<HTMLElement>(null);
  const recordId = record?.id;
  useEffect(() => {
    if (recordId && window.matchMedia(NARROW_SCREEN).matches) article.current?.scrollIntoView({ block: "start" });
  }, [recordId]);
  if (!record) return <p className="empty record-placeholder">Select a record to see where it is in the workflow.</p>;
  return (
    <article className="record-detail" aria-live="polite" ref={article}>
      <button className="detail-back" onClick={onBack}>
        <ArrowLeft size={16} /> Records
      </button>
      {record.kind === "incident" ? (
        <IncidentDetail incident={record.incident} {...props} />
      ) : (
        <ReviewDetail review={record.review} {...props} />
      )}
    </article>
  );
}
