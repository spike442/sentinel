import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { checkReviews } from "../api/reviews";
import type { Domain, WorkflowGraph } from "../model";
import { humanize } from "../workflow";
import { domainLabel } from "./DomainIcon";
import { RecordDetail, RecordList, visitedStates, type DomainRecord } from "./Records";
import { StateMachine } from "./StateMachine";

export function DomainView({
  domain,
  graph,
  records,
  error,
  selectedId,
  onSelectRecord,
  onCloseRecord,
  onRefresh,
  notify,
}: {
  domain: Domain;
  graph: WorkflowGraph | null;
  records: DomainRecord[];
  error: string;
  selectedId: string | null;
  onSelectRecord: (id: string | null) => void;
  onCloseRecord: () => void;
  onRefresh: () => void;
  notify: (message: string) => void;
}) {
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const counts = useMemo(() => {
    const totals: Record<string, number> = {};
    for (const record of records) totals[record.status] = (totals[record.status] ?? 0) + 1;
    return totals;
  }, [records]);
  const shown = selectedState ? records.filter((record) => record.status === selectedState) : records;
  const selected = records.find((record) => record.id === selectedId) ?? null;
  const visited = useMemo(() => new Set(visitedStates(selected)), [selected]);

  async function discover() {
    try {
      await checkReviews();
      notify("Pull request discovery queued.");
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Discovery failed.");
    }
  }

  return (
    <section className="domain-view" aria-label={`${domainLabel(domain)} workflow`}>
      {domain === "pr-review" && (
        <header className="domain-header">
          <button className="action-button" onClick={() => void discover()}>
            <RefreshCw size={14} /> Check now
          </button>
        </header>
      )}
      {domain === "sre" && (
        <header className="domain-header">
          <button className="action-button" onClick={onRefresh}>
            <RefreshCw size={14} /> Refresh
          </button>
        </header>
      )}
      {error && <p role="alert" className="error">{error}</p>}
      {graph ? (
        <StateMachine
          graph={graph}
          counts={counts}
          selectedState={selectedState}
          visited={visited}
          current={selected?.status ?? null}
          onSelectState={(state) => {
            setSelectedState(state);
            if (selected) onSelectRecord(null);
          }}
        />
      ) : (
        <p className="empty">Loading the workflow…</p>
      )}
      <div className={`domain-body ${selected ? "has-selection" : ""}`}>
        <section className="records-panel" aria-label="Records">
          <h3>{selectedState ? humanize(selectedState) : "All records"}</h3>
          <RecordList records={shown} selectedId={selectedId} onSelect={onSelectRecord} />
        </section>
        <RecordDetail record={selected} onBack={onCloseRecord} onRefresh={onRefresh} onError={notify} />
      </div>
    </section>
  );
}
