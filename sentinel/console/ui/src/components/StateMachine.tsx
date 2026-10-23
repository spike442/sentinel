import { useMemo } from "react";
import { PHONE_SCREEN, useMediaQuery } from "../hooks/useMediaQuery";
import type { WorkflowGraph } from "../model";
import { useStateTone } from "../tones";
import { classifyTransitions, humanize, layout, wrapText } from "../workflow";

type Point = { x: number; y: number };

const NOTE_CHAR_WIDTH = 7.2;

type Geometry = {
  vertical: boolean;
  nodeWidth: number;
  nodeHeight: number;
  rankGap: number;
  slotGap: number;
  lead: number;
  padding: number;
  trailing: number;
  notch: number;
  label: Point;
  count: Point;
  noteLine: number;
};

const HORIZONTAL: Geometry = {
  vertical: false,
  nodeWidth: 200,
  nodeHeight: 64,
  rankGap: 110,
  slotGap: 62,
  lead: 28,
  padding: 28,
  trailing: 62,
  notch: 12,
  label: { x: 18, y: 28 },
  count: { x: 18, y: 50 },
  noteLine: 15,
};

const VERTICAL: Geometry = {
  vertical: true,
  nodeWidth: 104,
  nodeHeight: 46,
  rankGap: 40,
  slotGap: 10,
  lead: 28,
  padding: 6,
  trailing: 26,
  notch: 8,
  label: { x: 9, y: 19 },
  count: { x: 9, y: 36 },
  noteLine: 0,
};

function nodeOutline({ nodeWidth: width, nodeHeight: height, notch }: Geometry): string {
  return `M ${notch} 0 H ${width} V ${height - notch} L ${width - notch} ${height} H 0 V ${notch} Z`;
}

function place(geometry: Geometry, along: number, across: number): Point {
  return geometry.vertical ? { x: across, y: along } : { x: along, y: across };
}

function spans(geometry: Geometry) {
  const along = geometry.vertical ? geometry.nodeHeight : geometry.nodeWidth;
  const across = geometry.vertical ? geometry.nodeWidth : geometry.nodeHeight;
  return { along, across };
}

function edgeCurve(geometry: Geometry, from: Point, to: Point): { d: string; middle: Point } {
  const { along, across } = spans(geometry);
  const startAlong = (geometry.vertical ? from.y : from.x) + along;
  const endAlong = geometry.vertical ? to.y : to.x;
  const middleAlong = (startAlong + endAlong) / 2;
  const startAcross = (geometry.vertical ? from.x : from.y) + across / 2;
  const endAcross = (geometry.vertical ? to.x : to.y) + across / 2;
  const p0 = place(geometry, startAlong, startAcross);
  const p1 = place(geometry, middleAlong, startAcross);
  const p2 = place(geometry, middleAlong, endAcross);
  const p3 = place(geometry, endAlong, endAcross);
  const d = `M ${p0.x} ${p0.y} C ${p1.x} ${p1.y}, ${p2.x} ${p2.y}, ${p3.x} ${p3.y}`;
  const middle = { x: (p0.x + 3 * p1.x + 3 * p2.x + p3.x) / 8, y: (p0.y + 3 * p1.y + 3 * p2.y + p3.y) / 8 };
  return { d, middle };
}

function initialMarker(geometry: Geometry, target: Point) {
  const { across } = spans(geometry);
  const along = geometry.vertical ? target.y : target.x;
  const middle = (geometry.vertical ? target.x : target.y) + across / 2;
  const dot = place(geometry, along - 22, middle);
  const start = place(geometry, along - 17, middle);
  const end = place(geometry, along - 2, middle);
  return { dot, start, end };
}

export function StateMachine({
  graph,
  counts,
  selectedState,
  visited,
  current,
  onSelectState,
}: {
  graph: WorkflowGraph;
  counts: Record<string, number>;
  selectedState: string | null;
  visited: Set<string>;
  current: string | null;
  onSelectState: (state: string | null) => void;
}) {
  const phone = useMediaQuery(PHONE_SCREEN);
  const stateTone = useStateTone();
  const geometry = phone ? VERTICAL : HORIZONTAL;
  const { placed, ranks, slots } = useMemo(() => layout(graph), [graph]);
  const { direct, forward, notes } = useMemo(() => classifyTransitions(graph, placed), [graph, placed]);
  const noteChars = Math.floor((geometry.nodeWidth + geometry.rankGap / 2) / NOTE_CHAR_WIDTH);
  const notesByState = useMemo(() => {
    const grouped = new Map<string, { note: (typeof notes)[number]; lines: string[] }[]>();
    for (const note of notes) {
      const lines = wrapText(note.text, noteChars);
      grouped.set(note.state, [...(grouped.get(note.state) ?? []), { note, lines }]);
    }
    return grouped;
  }, [notes, noteChars]);
  const lineCounts = [...notesByState.values()].map((items) => items.reduce((total, item) => total + item.lines.length, 0));
  const noteLines = geometry.vertical ? 0 : Math.max(0, ...lineCounts);
  const noteSpace = noteLines * geometry.noteLine + (noteLines ? 12 : 0);
  const slotGap = Math.max(geometry.slotGap, noteSpace + 8);
  const trailing = Math.max(geometry.trailing, noteSpace);
  const { along, across } = spans(geometry);
  const position = useMemo(() => {
    const positions = new Map<string, Point>();
    for (const item of placed) {
      const alongOffset = geometry.lead + item.rank * (along + geometry.rankGap);
      const acrossOffset = geometry.padding + item.slot * (across + slotGap);
      positions.set(item.state, place(geometry, alongOffset, acrossOffset));
    }
    return positions;
  }, [placed, geometry, along, across, slotGap]);
  const noteOverhang = geometry.vertical ? 0 : geometry.rankGap / 2;
  const alongTotal = geometry.lead + geometry.padding + ranks * along + (ranks - 1) * geometry.rankGap + noteOverhang;
  const acrossTotal = geometry.padding * 2 + slots * across + (slots - 1) * slotGap + trailing;
  const canvas = place(geometry, alongTotal, acrossTotal);
  const outline = nodeOutline(geometry);
  const initial = graph.transitions.find((edge) => edge.source === null);
  const initialTarget = initial ? position.get(initial.target) : undefined;
  const marker = initialTarget ? initialMarker(geometry, initialTarget) : null;
  const focus = selectedState ?? current;
  const spread = (edge: { source: string; target: string }) => {
    const from = position.get(edge.source);
    const to = position.get(edge.target);
    if (!from || !to) return Infinity;
    return geometry.vertical ? Math.abs(to.x - from.x) : Math.abs(to.y - from.y);
  };
  const touchesFocus = (edge: { source: string; target: string }) =>
    focus !== null && (edge.source === focus || edge.target === focus);
  const shown = direct.filter((edge) => forward.has(edge));
  const labelled = new Map<string, (typeof shown)[number]>();
  for (const edge of shown.filter(touchesFocus)) {
    const key = `${edge.source}-${edge.event}`;
    const kept = labelled.get(key);
    if (!kept || spread(edge) < spread(kept)) labelled.set(key, edge);
  }
  const noteClass = (related: string[]) => {
    if (focus === null) return "";
    return related.includes(focus) ? "highlighted" : "dimmed";
  };
  const toggle = (state: string) => onSelectState(selectedState === state ? null : state);

  return (
    <figure
      className={`state-machine ${geometry.vertical ? "vertical" : ""}`}
      aria-label={`${graph.domain} workflow state machine`}
    >
      <svg viewBox={`0 0 ${canvas.x} ${canvas.y}`} width={canvas.x} height={canvas.y} role="img">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" className="arrow-head" />
          </marker>
        </defs>
        {initial && marker && (
          <g className="initial">
            <circle cx={marker.dot.x} cy={marker.dot.y} r="5" />
            <line x1={marker.start.x} y1={marker.start.y} x2={marker.end.x} y2={marker.end.y} markerEnd="url(#arrow)" />
            <title>{humanize(initial.event)}</title>
          </g>
        )}
        {shown.map((edge, index) => {
          const from = position.get(edge.source);
          const to = position.get(edge.target);
          if (!from || !to) return null;
          const highlighted = touchesFocus(edge);
          const dimmed = focus !== null && !highlighted;
          const traversed = visited.has(edge.source) && visited.has(edge.target);
          const curve = edgeCurve(geometry, from, to);
          const classes = [
            "edge",
            highlighted ? "highlighted" : "",
            dimmed ? "dimmed" : "",
            traversed ? "traversed" : "",
          ].join(" ");
          return (
            <g key={`${edge.source}-${edge.event}-${edge.target}-${index}`}>
              <path d={curve.d} className={classes} markerEnd="url(#arrow)">
                <title>{`${humanize(edge.source)} → ${humanize(edge.target)}: ${humanize(edge.event)}`}</title>
              </path>
              {labelled.get(`${edge.source}-${edge.event}`) === edge && !geometry.vertical && (
                <text x={curve.middle.x} y={curve.middle.y - 6} className="edge-label">
                  {humanize(edge.event)}
                </text>
              )}
            </g>
          );
        })}
        {placed.map(({ state }) => {
          const point = position.get(state)!;
          const count = counts[state] ?? 0;
          const stateNotes = notesByState.get(state) ?? [];
          const noteRows = stateNotes.flatMap(({ note, lines }) => lines.map((line, index) => ({ note, line, index })));
          const classes = [
            "node",
            `tone-${stateTone(state)}`,
            selectedState === state ? "selected" : "",
            current === state ? "current" : "",
            visited.has(state) ? "visited" : "",
          ].join(" ");
          return (
            <g
              key={state}
              className={classes}
              transform={`translate(${point.x} ${point.y})`}
              onClick={() => toggle(state)}
              role="button"
              tabIndex={0}
              aria-pressed={selectedState === state}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                toggle(state);
              }}
            >
              <path d={outline} className="node-frame" />
              <text x={geometry.label.x} y={geometry.label.y} className="node-label">{humanize(state)}</text>
              <text x={geometry.count.x} y={geometry.count.y} className="node-count">
                {count === 1 ? "1 record" : `${count} records`}
              </text>
              {!geometry.vertical &&
                noteRows.map(({ note, line, index }, row) => (
                  <text
                    key={`${note.text}-${index}`}
                    x="0"
                    y={geometry.nodeHeight + 18 + row * geometry.noteLine}
                    className={`node-note ${noteClass(note.related)}`}
                  >
                    {line}
                    <title>{note.title}</title>
                  </text>
                ))}
              <title>{`${humanize(state)}: ${count}`}</title>
            </g>
          );
        })}
      </svg>
      {geometry.vertical && notes.length > 0 && (
        <figcaption>
          {notes.map((note) => (
            <span key={note.caption} title={note.title} className={noteClass(note.related)}>
              {note.caption}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}
