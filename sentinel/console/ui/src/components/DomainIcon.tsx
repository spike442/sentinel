import type { ComponentType } from "react";
import { Boxes, GitPullRequest } from "lucide-react";

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

function BullIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 16c-.6-1.4-.4-3.6 1.4-5 .8-.6 1.4-1.2 2-1.8C7.8 6.4 9.6 4.8 12 5c2.4.2 3.6 2.2 6.4 2.6 2 .3 3 1.8 2.4 4-.5 1.6-1.8 2.4-3.4 2.4l-5.2.4c-1.4.2-2.4 1.2-4 1-1.4-.2-2.2 1-3.6 1.2-.8.2-1.4 0-1.6-.6z" />
      <path d="M8.6 15.6 6.4 20" />
      <path d="m11.4 14.6.4 5.4" />
      <path d="m17.6 14 1.2 5.6" />
      <path d="m20.2 12.8 1 6.8" />
      <path d="M6.2 9.6c-2 .2-3.4-.8-3.6-3" />
      <path d="M7.8 8.6c-.4-2-1.4-3.4-2.6-3.8" />
      <path d="M20.2 8.2c1.8-.4 2.4-2.2 1.6-3.8" />
    </svg>
  );
}

const ICONS: Record<string, ComponentType<{ "aria-hidden"?: boolean }>> = {
  kubernetes: KubernetesIcon,
  "git-pull-request": GitPullRequest,
  bull: BullIcon,
};

export function DomainIcon({ icon }: { icon: string | undefined }) {
  const Icon = (icon && ICONS[icon]) || Boxes;
  return <Icon aria-hidden={true} />;
}
