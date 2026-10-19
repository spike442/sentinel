import { getJson, sendRequest } from "./client";
import { toIncident, type ApiIncident, type Incident } from "../model";

export async function loadIncidents(signal: AbortSignal): Promise<Incident[]> {
  const data = await getJson<{ incidents: ApiIncident[] }>("/api/incidents?limit=200", signal);
  return data.incidents.map(toIncident);
}

export function replayIncident(incident: Incident, prompt: string): Promise<void> {
  return sendRequest(`/api/incidents/replay/${incident.id}`, "POST", "Replay rejected", { prompt });
}

export function ignoreIncident(incident: Incident): Promise<void> {
  return sendRequest(`/api/incidents/${incident.id}/ignore`, "POST", "Ignore rejected");
}

export function deleteIncident(incident: Incident): Promise<void> {
  return sendRequest(`/api/incidents/${incident.id}`, "DELETE", "Delete rejected");
}

export function executeManualAction(incident: Incident, index: number): Promise<void> {
  return sendRequest(`/api/incidents/${incident.id}/manual-actions/execute`, "POST", "Manual action rejected", {
    action_index: index,
  });
}
