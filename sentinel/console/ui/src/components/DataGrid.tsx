import { useMemo, useState } from "react";
import { humanize } from "../workflow";

function cellText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function DataGrid({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  const [filter, setFilter] = useState("");
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [descending, setDescending] = useState(false);
  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const matching = needle
      ? rows.filter((row) => columns.some((column) => cellText(row[column]).toLowerCase().includes(needle)))
      : rows;
    if (!sortColumn) return matching;
    const sorted = [...matching].sort((left, right) =>
      cellText(left[sortColumn]).localeCompare(cellText(right[sortColumn]), undefined, { numeric: true }),
    );
    return descending ? sorted.reverse() : sorted;
  }, [rows, columns, filter, sortColumn, descending]);

  function sortBy(column: string) {
    if (sortColumn === column) setDescending((current) => !current);
    else {
      setSortColumn(column);
      setDescending(false);
    }
  }

  return (
    <div className="data-grid">
      <div className="data-grid-toolbar">
        <input
          className="data-grid-filter"
          type="search"
          placeholder="Filter rows"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          aria-label="Filter rows"
        />
        <span className="data-grid-count">
          {shown.length} / {rows.length} rows
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="empty">No rows.</p>
      ) : (
        <div className="data-grid-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} scope="col" aria-sort={sortColumn === column ? (descending ? "descending" : "ascending") : "none"}>
                    <button onClick={() => sortBy(column)}>
                      {humanize(column)}
                      {sortColumn === column ? (descending ? " ↓" : " ↑") : ""}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((row, index) => (
                <tr key={index}>
                  {columns.map((column) => {
                    const text = cellText(row[column]);
                    return (
                      <td key={column} title={text}>
                        {text}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
