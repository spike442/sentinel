import { getJson } from "./client";
import type { Domain, ManagedAgent, WorkflowGraph } from "../model";

export async function loadSentinelVersion(): Promise<string> {
  const data = await getJson<{ status: string; version: string }>("/api/healthz");
  return data.version;
}

export async function loadAgents(signal: AbortSignal): Promise<ManagedAgent[]> {
  const data = await getJson<{ agents: ManagedAgent[] }>("/api/agents", signal);
  return data.agents;
}

export function loadWorkflow(domain: Domain, signal: AbortSignal): Promise<WorkflowGraph> {
  return getJson<WorkflowGraph>(`/api/agents/${domain}/workflow`, signal);
}
