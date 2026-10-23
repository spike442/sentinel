import { useEffect, useState } from "react";
import type { DomainClient } from "../api/client";
import { loadWorkflow } from "../api/domains";
import type { WorkflowGraph } from "../model";

export function useWorkflow(client: DomainClient) {
  const [graph, setGraph] = useState<WorkflowGraph | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    loadWorkflow(client, controller.signal)
      .then((loaded) => {
        setGraph(loaded);
        setError("");
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Workflow unavailable.");
      });
    return () => controller.abort();
  }, [client]);
  return { graph, error };
}
