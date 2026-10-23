import type { DomainStatus } from "../api/domains";
import { DomainIcon } from "./DomainIcon";

function health(status: DomainStatus): { label: string; live: boolean; usable: boolean } {
  const { manifest } = status;
  if (!manifest) return { label: "unavailable", live: false, usable: false };
  if (!manifest.enabled) return { label: "disabled", live: false, usable: false };
  if (!manifest.running) return { label: "down", live: false, usable: true };
  const label = manifest.kind === "workflow" ? `${manifest.active} active` : "live";
  return { label, live: true, usable: true };
}

export function DomainTiles({
  domains,
  selected,
  onSelect,
}: {
  domains: DomainStatus[];
  selected: string | null;
  onSelect: (domain: string) => void;
}) {
  return (
    <nav className="agent-tiles" aria-label="Domains">
      {domains.map((status) => {
        const { id } = status.config;
        const state = health(status);
        const label = `${status.manifest?.label ?? id} · ${state.label}`;
        return (
          <button
            key={id}
            className={`agent-tile ${selected === id ? "selected" : ""}`}
            onClick={() => onSelect(id)}
            disabled={!state.usable}
            aria-pressed={selected === id}
            aria-label={label}
            title={label}
          >
            <span className={`tile-live ${state.live ? "" : "down"}`} aria-hidden="true" />
            <span className="tile-icon"><DomainIcon icon={status.manifest?.icon ?? status.config.icon} /></span>
          </button>
        );
      })}
    </nav>
  );
}
