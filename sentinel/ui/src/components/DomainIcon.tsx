import { GitPullRequest } from "lucide-react";
import type { Domain } from "../model";

const HEPTAGON = "12,2 19.82,5.77 21.75,14.23 16.34,21.01 7.66,21.01 2.25,14.23 4.18,5.77";
const SPOKES = [
  [12, 9.4, 12, 4.8],
  [14.03, 10.38, 17.63, 7.51],
  [14.53, 12.58, 19.02, 13.6],
  [13.13, 14.34, 15.12, 18.49],
  [10.87, 14.34, 8.88, 18.49],
  [9.47, 12.58, 4.98, 13.6],
  [9.97, 10.38, 6.37, 7.51],
];

export function domainLabel(domain: Domain): string {
  return domain === "sre" ? "SRE" : "PR review";
}

function KubernetesIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points={HEPTAGON} />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.4" />
      {SPOKES.map(([x1, y1, x2, y2]) => (
        <line key={`${x2}-${y2}`} x1={x1} y1={y1} x2={x2} y2={y2} />
      ))}
    </svg>
  );
}

export function DomainIcon({ domain }: { domain: Domain }) {
  return domain === "sre" ? <KubernetesIcon /> : <GitPullRequest aria-hidden="true" />;
}
