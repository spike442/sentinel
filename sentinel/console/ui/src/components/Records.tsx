import { Suspense, useEffect, useRef, useState } from "react";
import { ArrowLeft, Link2 } from "lucide-react";
import type { DomainClient } from "../api/client";
import { formatTimestamp, sortByTimestamp } from "../format";
import { NARROW_SCREEN } from "../hooks/useMediaQuery";
import { routeHash } from "../hooks/useRoute";
import type { DomainRecord, RecordAction } from "../model";
import { useStateTone } from "../tones";
import { humanize } from "../workflow";
import type { DetailProps, DomainModule, RunAction } from "../domains/types";
import { AttemptHistory, Timeline } from "./Attempts";
import { Block, BudgetChip, KeyValues, Section } from "./RecordSections";

export function visitedStates(record: DomainRecord | null, states: string[]): string[] {
  if (!record) return [];
  const known = new Set(states);
  const timeline = sortByTimestamp(record.timeline ?? []);
  const visited = timeline.map((entry) => entry.event).filter((event) => known.has(event));
  return [...visited, record.status];
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
  const stateTone = useStateTone();
  if (!records.length) return <p className="empty">No records in this state.</p>;
  return (
    <ul className="record-list">
      {records.map((record) => (
        <li key={record.id}>
          <button className={`record-row ${selectedId === record.id ? "selected" : ""}`} onClick={() => onSelect(record.id)}>
            <span className={`state-dot tone-${stateTone(record.status)}`} aria-hidden="true" />
            <span className="record-title">{record.title}</span>
            <span className="record-state">{humanize(record.status)}</span>
            <time className="record-time">{formatTimestamp(record.updated_at)}</time>
          </button>
        </li>
      ))}
    </ul>
  );
}

function operatorPrompt(action: RecordAction): string | null {
  if (!action.prompt) return "";
  const answer = window.prompt(action.prompt.message);
  if (answer === null) return null;
  const prompt = answer.trim();
  return action.prompt.required && !prompt ? null : prompt;
}

function useRecordActions(client: DomainClient, record: DomainRecord, onDone: () => void, onError: (message: string) => void) {
  const [busy, setBusy] = useState(false);
  const run: RunAction = async (action, body = {}) => {
    setBusy(true);
    try {
      await client.send(`/records/${encodeURIComponent(record.id)}/actions/${action}`, "POST", `${humanize(action)} rejected`, body);
      onDone();
    } catch (error) {
      onError(error instanceof Error ? error.message : "The action failed.");
    } finally {
      setBusy(false);
    }
  };
  function trigger(action: RecordAction) {
    if (action.confirm && !window.confirm(action.confirm)) return;
    const prompt = operatorPrompt(action);
    if (prompt !== null) void run(action.name, { prompt });
  }
  return { busy, run, trigger };
}

function GenericDetail({ record, actions }: DetailProps) {
  const attempts = record.attempts ?? [];
  const timeline = record.timeline ?? [];
  return (
    <>
      <div className="detail-actions">{actions}</div>
      {timeline.length > 0 && (
        <Section title="Timeline" count={timeline.length} open>
          <Timeline events={timeline} label="Record timeline" />
        </Section>
      )}
      {attempts.length > 0 && (
        <Section title="Attempts" count={attempts.length} open>
          <AttemptHistory attempts={attempts} renderResult={(result) => <Block value={result} />} />
        </Section>
      )}
      <Section title="Record" open>
        <KeyValues values={{ id: record.id, workflow: record.workflow_id, updated: formatTimestamp(record.updated_at) }} />
        <Block value={record} />
      </Section>
    </>
  );
}

export function RecordDetail({
  record,
  client,
  module,
  onBack,
  onRefresh,
  onError,
}: {
  record: DomainRecord | null;
  client: DomainClient;
  module: DomainModule;
  onBack: () => void;
  onRefresh: () => void;
  onError: (message: string) => void;
}) {
  const article = useRef<HTMLElement>(null);
  const stateTone = useStateTone();
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
      <header className="detail-header">
        <h3>{record.title}</h3>
        <div className="detail-chips">
          <BudgetChip budget={record.tool_budget} />
          <span className={`state-chip tone-${stateTone(record.status)}`}>{humanize(record.status)}</span>
        </div>
      </header>
      <RecordBody key={record.id} record={record} client={client} module={module} onRefresh={onRefresh} onError={onError} />
    </article>
  );
}

function RecordBody({
  record,
  client,
  module,
  onRefresh,
  onError,
}: {
  record: DomainRecord;
  client: DomainClient;
  module: DomainModule;
  onRefresh: () => void;
  onError: (message: string) => void;
}) {
  const { busy, run, trigger } = useRecordActions(client, record, onRefresh, onError);
  const handled = new Set(module.handledActions ?? []);
  const links = (record.links ?? []).map((link) => (
    <a
      key={`${link.domain}/${link.workflow}/${link.record_id}`}
      className="action-button"
      href={routeHash({ domain: link.domain, view: link.workflow, recordId: link.record_id })}
    >
      <Link2 size={14} /> {link.label}
    </a>
  ));
  const buttons = record.actions
    .filter((action) => !handled.has(action.name))
    .map((action) => (
      <button
        key={action.name}
        className={`action-button ${action.tone === "default" ? "" : action.tone}`}
        disabled={busy}
        onClick={() => trigger(action)}
      >
        {action.label}
      </button>
    ));
  const Detail = module.Detail ?? GenericDetail;
  return (
    <Suspense fallback={<p className="empty">Loading the record view…</p>}>
      <Detail record={record} actions={<>{links}{buttons}</>} run={run} busy={busy} />
    </Suspense>
  );
}
