import type { WorkflowGraph, WorkflowTransition } from "./model";

export function humanize(name: string): string {
  const spaced = name.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

type PlacedState = { state: string; rank: number; slot: number };

export function layout(graph: WorkflowGraph): { placed: PlacedState[]; ranks: number; slots: number } {
  const initial = graph.transitions.find((edge) => edge.source === null)?.target ?? graph.states[0];
  const rankOf = new Map<string, number>([[initial, 0]]);
  const queue = [initial];
  while (queue.length) {
    const state = queue.shift()!;
    const next = graph.transitions.filter((edge) => edge.source === state);
    for (const edge of next) {
      if (rankOf.has(edge.target)) continue;
      rankOf.set(edge.target, rankOf.get(state)! + 1);
      queue.push(edge.target);
    }
  }
  const deepest = Math.max(...rankOf.values());
  const ranks = new Map<number, string[]>();
  for (const state of graph.states) {
    const rank = rankOf.get(state) ?? deepest + 1;
    const members = ranks.get(rank) ?? [];
    members.push(state);
    ranks.set(rank, members);
  }
  const placed: PlacedState[] = [];
  for (const [rank, members] of ranks) {
    members.forEach((state, slot) => placed.push({ state, rank, slot }));
  }
  const slots = Math.max(...[...ranks.values()].map((members) => members.length));
  return { placed, ranks: ranks.size, slots };
}

export type DirectTransition = WorkflowTransition & { source: string };

export type TransitionNote = { state: string; text: string; caption: string; title: string; related: string[] };

const FAN_IN_SOURCES = 3;

function events(edges: WorkflowTransition[]): string {
  const names = [...new Set(edges.map((edge) => humanize(edge.event).toLowerCase()))];
  return names.join(", ");
}

function groupBy<T>(items: T[], key: (item: T) => string): Map<string, T[]> {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const name = key(item);
    const members = groups.get(name) ?? [];
    members.push(item);
    groups.set(name, members);
  }
  return groups;
}

export function classifyTransitions(
  graph: WorkflowGraph,
  placed: PlacedState[],
): { direct: DirectTransition[]; forward: Set<DirectTransition>; notes: TransitionNote[] } {
  const rankOf = new Map(placed.map((item) => [item.state, item.rank]));
  const direct = graph.transitions.filter(
    (edge): edge is DirectTransition => edge.source !== null && edge.source !== "*",
  );
  const forward = new Set(direct.filter((edge) => (rankOf.get(edge.target) ?? 0) > (rankOf.get(edge.source) ?? 0)));
  const returning = direct.filter((edge) => !forward.has(edge));
  const notes: TransitionNote[] = [];
  for (const [target, edges] of groupBy(returning, (edge) => edge.target)) {
    const sources = [...new Set(edges.map((edge) => edge.source))];
    const label = humanize(target).toLowerCase();
    if (sources.length >= FAN_IN_SOURCES) {
      const names = sources.map((source) => humanize(source).toLowerCase()).join(", ");
      notes.push({
        state: target,
        text: `← from ${sources.length} states · ${events(edges)}`,
        caption: `${sources.length} states → ${label} · ${events(edges)}`,
        title: `From ${names}`,
        related: [target, ...sources],
      });
      continue;
    }
    for (const [source, sourceEdges] of groupBy(edges, (edge) => edge.source)) {
      notes.push({
        state: source,
        text: `→ ${label} · ${events(sourceEdges)}`,
        caption: `${humanize(source).toLowerCase()} → ${label} · ${events(sourceEdges)}`,
        title: `${humanize(source)} → ${humanize(target)}`,
        related: [source, target],
      });
    }
  }
  const fromAny = graph.transitions.filter((edge) => edge.source === "*");
  for (const [target, edges] of groupBy(fromAny, (edge) => edge.target)) {
    const label = humanize(target).toLowerCase();
    notes.push({
      state: target,
      text: `← from any state · ${events(edges)}`,
      caption: `any state → ${label} · ${events(edges)}`,
      title: `Any state → ${humanize(target)}`,
      related: [target],
    });
  }
  return { direct, forward, notes };
}

export function wrapText(text: string, maxChars: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(" ")) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length > maxChars && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}
