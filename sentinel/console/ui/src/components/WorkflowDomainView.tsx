import { useCallback, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { DomainClient } from "../api/client";
import type { DomainEvent } from "../domains/types";
import { workflowModule } from "../domains/registry";
import { usePolledResource } from "../hooks/usePolledResource";
import { useWorkflow } from "../hooks/useWorkflow";
import type { DomainRecord, WorkflowSummary } from "../model";
import { ToneProvider } from "../tones";
import { humanize } from "../workflow";
import { RecordDetail, RecordList, visitedStates } from "./Records";
import { StateMachine } from "./StateMachine";

const NO_RECORDS: DomainRecord[] = [];

export function WorkflowDomainView({
  domain,
  workflow,
  client,
  domainClient,
  selectedId,
  onSelectRecord,
  onCloseRecord,
  notify,
}: {
  domain: string;
  workflow: WorkflowSummary;
  client: DomainClient;
  domainClient: DomainClient;
  selectedId: string | null;
  onSelectRecord: (id: string | null) => void;
  onCloseRecord: () => void;
  notify: (message: string) => void;
}) {
  const module = workflowModule(domain, workflow.id);
  const [refreshToken, setRefreshToken] = useState(0);
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const loadRecords = useCallback(
    async (signal: AbortSignal) => {
      const data = await client.getJson<{ records: DomainRecord[] }>("/records?limit=200", signal);
      return data.records;
    },
    [client],
  );
  const recordsState = usePolledResource(true, refreshToken, loadRecords, NO_RECORDS, `${workflow.label} records unavailable.`);
  const records = recordsState.value;
  const { graph, error: graphError } = useWorkflow(client);
  const refresh = () => setRefreshToken((token) => token + 1);
  const counts = useMemo(() => {
    const totals: Record<string, number> = {};
    for (const record of records) totals[record.status] = (totals[record.status] ?? 0) + 1;
    return totals;
  }, [records]);
  const shown = selectedState ? records.filter((record) => record.status === selectedState) : records;
  const selected = records.find((record) => record.id === selectedId) ?? null;
  const visited = useMemo(() => new Set(visitedStates(selected, graph?.states ?? [])), [selected, graph]);

  async function emit(event: DomainEvent) {
    try {
      await domainClient.send(`/events/${event.name}`, "POST", `${event.label} failed`);
      notify(event.done);
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : `${event.label} failed.`);
    }
  }

  return (
    <ToneProvider tones={graph?.tones}>
      <section className="domain-view" aria-label={`${workflow.label} workflow`}>
        <header className="domain-header">
          {module.events?.map((event) => (
            <button key={event.name} className="action-button" onClick={() => void emit(event)}>
              <RefreshCw size={14} /> {event.label}
            </button>
          ))}
          <button className="action-button" onClick={refresh}>
            <RefreshCw size={14} /> Refresh
          </button>
        </header>
        {(recordsState.error || graphError) && <p role="alert" className="error">{recordsState.error || graphError}</p>}
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
          <RecordDetail
            record={selected}
            client={client}
            module={module}
            onBack={onCloseRecord}
            onRefresh={refresh}
            onError={notify}
          />
        </div>
      </section>
    </ToneProvider>
  );
}
