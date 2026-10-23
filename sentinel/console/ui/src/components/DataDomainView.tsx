import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { DomainClient } from "../api/client";
import { useResource } from "../hooks/useResource";
import type { DatasetRows, DatasetSummary, DomainManifest } from "../model";
import { DataGrid } from "./DataGrid";

const NO_DATASETS: DatasetSummary[] = [];
const NO_DATES: string[] = [];

export function DataDomainView({
  manifest,
  client,
  selected,
  onSelect,
}: {
  manifest: DomainManifest;
  client: DomainClient;
  selected: string | null;
  onSelect: (dataset: string) => void;
}) {
  const [refreshToken, setRefreshToken] = useState(0);
  const [tradeDate, setTradeDate] = useState("");
  const [data, setData] = useState<DatasetRows | null>(null);
  const [error, setError] = useState("");
  const loadDatasets = useCallback(
    async (signal: AbortSignal) => (await client.getJson<{ datasets: DatasetSummary[] }>("/datasets", signal)).datasets,
    [client],
  );
  const loadDates = useCallback(
    async (signal: AbortSignal) => (await client.getJson<{ trade_dates: string[] }>("/trade-dates", signal)).trade_dates,
    [client],
  );
  const datasets = useResource(loadDatasets, refreshToken, NO_DATASETS, `${manifest.label} datasets unavailable.`);
  const dates = useResource(loadDates, refreshToken, NO_DATES, "Trade dates unavailable.");
  const current = datasets.value.find((dataset) => dataset.name === selected) ?? datasets.value[0] ?? null;
  const currentName = current?.name;
  const tradeDated = current?.trade_dated ?? false;

  useEffect(() => {
    if (!currentName) return;
    const controller = new AbortController();
    const query = tradeDated && tradeDate ? `?trade_date=${tradeDate}` : "";
    client
      .getJson<DatasetRows>(`/datasets/${currentName}${query}`, controller.signal)
      .then((loaded) => {
        setData(loaded);
        setError("");
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setData(null);
        setError(reason instanceof Error ? reason.message : "Dataset unavailable.");
      });
    return () => controller.abort();
  }, [client, currentName, tradeDated, tradeDate, refreshToken]);

  return (
    <section className="domain-view" aria-label={`${manifest.label} data`}>
      <header className="domain-header data-header">
        <nav className="dataset-tabs" aria-label="Datasets">
          {datasets.value.map((dataset) => (
            <button
              key={dataset.name}
              className={`dataset-tab ${current?.name === dataset.name ? "selected" : ""}`}
              aria-pressed={current?.name === dataset.name}
              onClick={() => onSelect(dataset.name)}
            >
              {dataset.label}
            </button>
          ))}
        </nav>
        {current?.trade_dated && (
          <select
            className="trade-date"
            value={tradeDate}
            onChange={(event) => setTradeDate(event.target.value)}
            aria-label="Trade date"
          >
            <option value="">Latest trade date</option>
            {dates.value.map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        )}
        <button className="action-button" onClick={() => setRefreshToken((token) => token + 1)}>
          <RefreshCw size={14} /> Refresh
        </button>
      </header>
      {(datasets.error || error) && <p role="alert" className="error">{datasets.error || error}</p>}
      {data && current && data.name === current.name && (
        <section className="records-panel" aria-label={data.label}>
          <h3>
            {data.label}
            {data.trade_date ? ` · ${data.trade_date}` : ""}
          </h3>
          <DataGrid columns={data.columns} rows={data.rows} />
        </section>
      )}
    </section>
  );
}
