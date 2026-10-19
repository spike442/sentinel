import { useEffect, useMemo, useRef, useState } from "react";
import { CircleDot } from "lucide-react";
import { loadIncidents } from "./api/incidents";
import { loadReviews } from "./api/reviews";
import { loadAgents, loadSentinelVersion } from "./api/sentinel";
import { AgentTiles } from "./components/AgentTiles";
import { ArcReactor } from "./components/ArcReactor";
import { DomainView } from "./components/DomainView";
import { HudClock } from "./components/HudClock";
import { incidentRecord, reviewRecord } from "./components/Records";
import { usePolledResource } from "./hooks/usePolledResource";
import { useRoute } from "./hooks/useRoute";
import { useWorkflow } from "./hooks/useWorkflow";
import type { Domain, Incident, ManagedAgent, PullRequestReview } from "./model";
import { isActive } from "./workflow";

const NO_AGENTS: ManagedAgent[] = [];
const NO_INCIDENTS: Incident[] = [];
const NO_REVIEWS: PullRequestReview[] = [];

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

export function App() {
  const [version, setVersion] = useState("—");
  const [refreshToken, setRefreshToken] = useState(0);
  const { notification, notify } = useNotification();
  const { route, navigate, back } = useRoute();

  useEffect(() => {
    loadSentinelVersion()
      .then(setVersion)
      .catch(() => setVersion("—"));
  }, []);

  const agentsState = usePolledResource(true, refreshToken, loadAgents, NO_AGENTS, "Agent list unavailable.");
  const agents = agentsState.value;
  const enabledAgents = useMemo(() => agents.filter((agent) => agent.enabled), [agents]);
  const sreEnabled = enabledAgents.some((agent) => agent.domain === "sre");
  const reviewEnabled = enabledAgents.some((agent) => agent.domain === "pr-review");
  const incidentsState = usePolledResource(sreEnabled, refreshToken, loadIncidents, NO_INCIDENTS, "Incidents unavailable.");
  const reviewsState = usePolledResource(reviewEnabled, refreshToken, loadReviews, NO_REVIEWS, "Reviews unavailable.");
  const routedDomain = enabledAgents.find((agent) => agent.domain === route.domain)?.domain;
  const domain = routedDomain ?? enabledAgents[0]?.domain ?? null;
  const { graph, error: graphError } = useWorkflow(domain);

  const records = useMemo(
    () => ({ sre: incidentsState.value.map(incidentRecord), "pr-review": reviewsState.value.map(reviewRecord) }),
    [incidentsState.value, reviewsState.value],
  );
  const activeCounts = {
    sre: records.sre.filter((record) => isActive(record.status)).length,
    "pr-review": records["pr-review"].filter((record) => isActive(record.status)).length,
  };
  const domainError = domain === "sre" ? incidentsState.error : reviewsState.error;
  const selectedId = routedDomain ? route.recordId : null;

  function selectDomain(next: Domain) {
    if (next !== domain) navigate({ domain: next, recordId: null });
  }

  function selectRecord(current: Domain, recordId: string | null) {
    if (recordId === selectedId) return;
    navigate({ domain: current, recordId }, recordId === null || selectedId !== null);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="brand">
          <ArcReactor />
        </span>
        <AgentTiles agents={agents} activeCounts={activeCounts} selected={domain} onSelect={selectDomain} />
        <div className="app-readout">
          <HudClock />
          <small className="app-version">v{version}</small>
        </div>
      </header>
      {agentsState.error && <p role="alert" className="error">{agentsState.error}</p>}
      {notification && (
        <div className="status-toast" role="status">
          <CircleDot size={14} /> {notification}
        </div>
      )}
      {domain ? (
        <DomainView
          key={domain}
          domain={domain}
          graph={graph}
          records={records[domain]}
          error={domainError || graphError}
          selectedId={selectedId}
          onSelectRecord={(recordId) => selectRecord(domain, recordId)}
          onCloseRecord={() => back({ domain, recordId: null })}
          onRefresh={() => setRefreshToken((token) => token + 1)}
          notify={notify}
        />
      ) : (
        <p className="empty">No agents are running.</p>
      )}
    </div>
  );
}
