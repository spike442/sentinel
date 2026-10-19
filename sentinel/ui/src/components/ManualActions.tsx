import { useState, type ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { executeManualAction } from "../api/incidents";
import { formatTimestamp } from "../format";
import { INCIDENT_STATUS, type Incident, type ManualAction, type ManualActionRun } from "../model";

export function ManualActionCard({ action, children }: { action: ManualAction; children?: ReactNode }) {
  return (
    <div className="manual-action">
      <strong>{action.title}</strong>
      <pre className="manual-command">
        <code>$ {action.command}</code>
      </pre>
      <p>{action.reason}</p>
      <small>Validation: {action.validation}</small>
      {children}
    </div>
  );
}

function ManualRun({ run }: { run: ManualActionRun }) {
  return (
    <div className="manual-run">
      <div>
        <strong>
          {run.status ?? "unknown"}
          {typeof run.exit_code === "number" && ` · exit ${run.exit_code}`}
        </strong>
        <small>{formatTimestamp(run.at ?? run.claim_at)}</small>
      </div>
      <code>{run.command ?? "manual action"}</code>
      {run.error && <small className="manual-run-error">{run.error}</small>}
      {run.reason && <small className="manual-run-error">{run.reason}</small>}
      {run.stdout && (
        <pre className="data-block">
          <code>{run.stdout}</code>
        </pre>
      )}
      {run.stderr && (
        <pre className="data-block stderr">
          <code>{run.stderr}</code>
        </pre>
      )}
    </div>
  );
}

export function ManualActions({
  incident,
  onRefresh,
  onError,
}: {
  incident: Incident;
  onRefresh: () => void;
  onError: (message: string) => void;
}) {
  const [running, setRunning] = useState<number | null>(null);
  const canApprove = incident.status === INCIDENT_STATUS.BLOCKED && incident.manualActions.length > 0;
  const runs = incident.manualActionHistory;
  if (!canApprove && !runs.length) return null;

  async function execute(index: number) {
    if (!window.confirm(`Approve and run this command?\n\n$ ${incident.manualActions[index].command}`)) return;
    setRunning(index);
    try {
      await executeManualAction(incident, index);
      onRefresh();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Manual action failed.");
    } finally {
      setRunning(null);
    }
  }

  return (
    <section className="manual-actions" aria-label="Manual actions and runs">
      {canApprove && (
        <>
          <div className="detail-section-title">
            <ShieldAlert size={15} /> Manual action approval
          </div>
          <small className="incident-updated">Incident updated: {formatTimestamp(incident.updated)}</small>
          {incident.manualActions.map((action, index) => {
            const lastRun = runs.filter((run) => run.action_index === index).at(-1);
            return (
              <ManualActionCard action={action} key={`${action.command}-${index}`}>
                {lastRun && (
                  <small className="manual-action-result">
                    Last run: {lastRun.status ?? "unknown"}
                    {typeof lastRun.exit_code === "number" && ` (exit ${lastRun.exit_code})`}
                    {lastRun.error ? ` — ${lastRun.error}` : ""}
                  </small>
                )}
                <button className="action-button" onClick={() => void execute(index)} disabled={running !== null}>
                  {running === index ? "Running…" : "Approve & run"}
                </button>
              </ManualActionCard>
            );
          })}
        </>
      )}
      {runs.length > 0 && (
        <div className="manual-runs" aria-label="Manual action runs">
          {runs
            .slice()
            .reverse()
            .map((run, index) => (
              <ManualRun run={run} key={`${run.at ?? run.claim_at ?? ""}-${index}`} />
            ))}
        </div>
      )}
    </section>
  );
}
