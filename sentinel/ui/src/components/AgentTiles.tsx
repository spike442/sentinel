import { DomainIcon, domainLabel } from "./DomainIcon";
import type { Domain, ManagedAgent } from "../model";

export function AgentTiles({
  agents,
  activeCounts,
  selected,
  onSelect,
}: {
  agents: ManagedAgent[];
  activeCounts: Record<string, number>;
  selected: Domain | null;
  onSelect: (domain: Domain) => void;
}) {
  return (
    <nav className="agent-tiles" aria-label="Running agents">
      {agents.map((agent) => {
        const active = activeCounts[agent.domain] ?? 0;
        const health = agent.enabled ? (agent.running ? `${active} active` : "down") : "disabled";
        const label = `${domainLabel(agent.domain)} · ${health}`;
        const live = agent.enabled && agent.running;
        return (
          <button
            key={agent.domain}
            className={`agent-tile ${selected === agent.domain ? "selected" : ""}`}
            onClick={() => onSelect(agent.domain)}
            disabled={!agent.enabled}
            aria-pressed={selected === agent.domain}
            aria-label={label}
            title={label}
          >
            <span className={`tile-live ${live ? "" : "down"}`} aria-hidden="true" />
            <span className="tile-icon"><DomainIcon domain={agent.domain} /></span>
          </button>
        );
      })}
    </nav>
  );
}
