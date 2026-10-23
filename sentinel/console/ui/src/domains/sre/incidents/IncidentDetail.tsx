import { ExternalLink } from "lucide-react";
import { AttemptHistory, Timeline } from "../../../components/Attempts";
import { KeyValues, Section, ToolBudgetPanel, budgetExhausted } from "../../../components/RecordSections";
import { formatTimestamp } from "../../../format";
import type { DetailProps } from "../../types";
import { DiagnosisView } from "./DiagnosisView";
import { ManualActions } from "./ManualActions";
import { toIncident, type IncidentAttemptResult, type IncidentRecord } from "./model";

function IncidentAttempt({ result }: { result: IncidentAttemptResult }) {
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

export default function IncidentDetail({ record, actions, run }: DetailProps) {
  const incident = toIncident(record as IncidentRecord);
  const canApprove = record.actions.some((action) => action.name === "manual-action");
  return (
    <>
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
        {actions}
      </div>
      <ManualActions incident={incident} canApprove={canApprove} run={run} />
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
        <AttemptHistory attempts={incident.attempts} renderResult={(result) => <IncidentAttempt result={result} />} />
      </Section>
      <Section title="Alert">
        <h4>Labels</h4>
        <KeyValues values={incident.alertLabels} />
        <h4>Annotations</h4>
        <KeyValues values={incident.alertAnnotations} />
        <h4>Alert record</h4>
        <KeyValues values={{ fingerprint: incident.fingerprint, starts: incident.startsAt, ends: incident.endsAt }} />
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
