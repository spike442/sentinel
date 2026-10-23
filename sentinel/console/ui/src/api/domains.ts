import { domainClient, getJson, type DomainClient } from "./client";
import type { DomainConfig, DomainManifest, WorkflowGraph, WorkflowView } from "../model";

export type DomainStatus = {
  config: DomainConfig;
  client: DomainClient;
  manifest: DomainManifest | null;
  error: string;
};

export async function loadDomainConfig(signal: AbortSignal): Promise<DomainConfig[]> {
  const data = await getJson<{ domains: DomainConfig[] }>("/domains.json", signal);
  return data.domains;
}

export type DomainEndpoint = { config: DomainConfig; client: DomainClient };

export function domainEndpoints(configs: DomainConfig[]): DomainEndpoint[] {
  return configs.map((config) => ({ config, client: domainClient(config.api) }));
}

export async function loadDomainStatuses(endpoints: DomainEndpoint[], signal: AbortSignal): Promise<DomainStatus[]> {
  const loaded = await Promise.allSettled(endpoints.map(({ client }) => client.getJson<DomainManifest>("/manifest", signal)));
  return endpoints.map(({ config, client }, index) => {
    const result = loaded[index];
    if (result.status === "fulfilled") return { config, client, manifest: result.value, error: "" };
    const reason = result.reason instanceof Error ? result.reason.message : "unavailable";
    return { config, client, manifest: null, error: reason };
  });
}

export async function loadWorkflow(client: DomainClient, signal: AbortSignal): Promise<WorkflowGraph> {
  const view = await client.getJson<WorkflowView>("/workflow", signal);
  return { ...view, states: view.states.map((state) => state.name) };
}
