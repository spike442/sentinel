export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function timestampValue(value: string | null | undefined): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed;
}

export function sortByTimestamp<T extends { at: string }>(
  entries: T[],
  newestFirst = false,
): T[] {
  return [...entries].sort((left, right) => {
    const difference = timestampValue(left.at) - timestampValue(right.at);
    return newestFirst ? -difference : difference;
  });
}
