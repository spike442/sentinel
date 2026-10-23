import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleDot } from "lucide-react";
import { domainEndpoints, loadDomainConfig, loadDomainStatuses, type DomainStatus } from "./api/domains";
import { ArcReactor } from "./components/ArcReactor";
import { DataDomainView } from "./components/DataDomainView";
import { DomainTiles } from "./components/DomainTiles";
import { HudClock } from "./components/HudClock";
import { DomainWorkflows } from "./components/DomainWorkflows";
import { usePolledResource } from "./hooks/usePolledResource";
import { useResource } from "./hooks/useResource";
import { useRoute } from "./hooks/useRoute";
import type { DomainConfig } from "./model";

const NO_CONFIG: DomainConfig[] = [];
const NO_DOMAINS: DomainStatus[] = [];

function useNotification() {
  const [notification, setNotification] = useState("");
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  function notify(message: string) {
    window.clearTimeout(timer.current);
    setNotification(message);
    timer.current = window.setTimeout(() => setNotification(""), 4500);
  }
  return { notification, notify };
}

function usable(status: DomainStatus): boolean {
  return Boolean(status.manifest?.enabled);
}

export function App() {
  const { notification, notify } = useNotification();
  const { route, navigate, back } = useRoute();
  const config = useResource(loadDomainConfig, 0, NO_CONFIG, "Domain configuration unavailable.");
  const endpoints = useMemo(() => domainEndpoints(config.value), [config.value]);
  const loadStatuses = useCallback((signal: AbortSignal) => loadDomainStatuses(endpoints, signal), [endpoints]);
  const statuses = usePolledResource(endpoints.length > 0, endpoints.length, loadStatuses, NO_DOMAINS, "Domains unavailable.");
  const domains = statuses.value;
  const routed = domains.find((status) => status.config.id === route.domain && usable(status));
  const current = routed ?? domains.find(usable) ?? null;
  const manifest = current?.manifest ?? null;
  const view = routed ? route.view : null;
  const selectedId = routed ? route.recordId : null;

  function selectDomain(next: string) {
    if (next !== current?.config.id) navigate({ domain: next, view: null, recordId: null });
  }

  function selectRecord(domain: string, workflow: string, recordId: string | null) {
    if (workflow === view && recordId === selectedId) return;
    navigate({ domain, view: workflow, recordId }, recordId === null || selectedId !== null);
  }

  const error = config.error || statuses.error;
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand">
          <ArcReactor />
        </span>
        <DomainTiles domains={domains} selected={current?.config.id ?? null} onSelect={selectDomain} />
        <div className="app-readout">
          <HudClock />
          <small className="app-version">v{manifest?.version ?? "—"}</small>
        </div>
      </header>
      {error && <p role="alert" className="error">{error}</p>}
      {notification && (
        <div className="status-toast" role="status">
          <CircleDot size={14} /> {notification}
        </div>
      )}
      {current && manifest?.kind === "workflow" && (
        <section className="domain-view" aria-label={manifest.label}>
          <DomainWorkflows
            key={current.config.id}
            config={current.config}
            manifest={manifest}
            client={current.client}
            view={view}
            selectedId={selectedId}
            onSelectView={(workflow) => navigate({ domain: current.config.id, view: workflow, recordId: null })}
            onSelectRecord={(workflow, recordId) => selectRecord(current.config.id, workflow, recordId)}
            onCloseRecord={(workflow) => back({ domain: current.config.id, view: workflow, recordId: null })}
            notify={notify}
          />
        </section>
      )}
      {current && manifest?.kind === "data" && (
        <DataDomainView
          key={current.config.id}
          manifest={manifest}
          client={current.client}
          selected={view}
          onSelect={(dataset) => navigate({ domain: current.config.id, view: dataset, recordId: null }, true)}
        />
      )}
      {!current && <p className="empty">No domains are available.</p>}
    </div>
  );
}
