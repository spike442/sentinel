const SEGMENTS = Array.from({ length: 10 }, (_, index) => index * 36);

export function ArcReactor() {
  return (
    <svg className="arc-reactor" viewBox="0 0 64 64" aria-hidden="true">
      <circle className="arc-halo" cx="32" cy="32" r="30" />
      <g className="arc-ring arc-ring-outer">
        <circle cx="32" cy="32" r="27" />
      </g>
      <g className="arc-ring arc-ring-segments">
        {SEGMENTS.map((angle) => (
          <rect key={angle} x="29.5" y="10" width="5" height="7" rx="1" transform={`rotate(${angle} 32 32)`} />
        ))}
      </g>
      <g className="arc-ring arc-ring-inner">
        <circle cx="32" cy="32" r="14" />
      </g>
      <circle className="arc-core" cx="32" cy="32" r="7" />
    </svg>
  );
}
