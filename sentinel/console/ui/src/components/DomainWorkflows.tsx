import { useMemo } from "react";
import { domainClient, type DomainClient } from "../api/client";
import type { DomainConfig, DomainManifest } from "../model";
import { WorkflowDomainView } from "./WorkflowDomainView";

export function DomainWorkflows({
  config,
  manifest,
  client,
  view,
  selectedId,
  onSelectView,
  onSelectRecord,
  onCloseRecord,
  notify,
}: {
  config: DomainConfig;
  manifest: DomainManifest;
  client: DomainClient;
  view: string | null;
  selectedId: string | null;
  onSelectView: (workflow: string) => void;
  onSelectRecord: (workflow: string, recordId: string | null) => void;
  onCloseRecord: (workflow: string) => void;
  notify: (message: string) => void;
}) {
  const workflows = manifest.workflows ?? [];
  const current = workflows.find((workflow) => workflow.id === view) ?? workflows[0] ?? null;
  const currentId = current?.id;
  const workflowClient = useMemo(
    () => (currentId ? domainClient(`${config.api}/${currentId}`) : null),
    [config.api, currentId],
  );
  if (!current || !workflowClient) return <p className="empty">{manifest.label} has no workflows.</p>;
  const routedRecord = current.id === view ? selectedId : null;
  return (
    <>
      {workflows.length > 1 && (
        <nav className="dataset-tabs workflow-tabs" aria-label={`${manifest.label} workflows`}>
          {workflows.map((workflow) => (
            <button
              key={workflow.id}
              className={`dataset-tab ${workflow.id === current.id ? "selected" : ""}`}
              aria-pressed={workflow.id === current.id}
              onClick={() => onSelectView(workflow.id)}
            >
              <span className={`state-dot tone-${workflow.running ? "done" : "failed"}`} aria-hidden="true" />
              {workflow.label} · {workflow.active}
            </button>
          ))}
        </nav>
      )}
      <WorkflowDomainView
        key={`${config.id}/${current.id}`}
        domain={config.id}
        workflow={current}
        client={workflowClient}
        domainClient={client}
        selectedId={routedRecord}
        onSelectRecord={(recordId) => onSelectRecord(current.id, recordId)}
        onCloseRecord={() => onCloseRecord(current.id)}
        notify={notify}
      />
    </>
  );
}
