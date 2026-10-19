import { useEffect, useState } from "react";
import { loadWorkflow } from "../api/sentinel";
import type { Domain, WorkflowGraph } from "../model";

export function useWorkflow(domain: Domain | null) {
  const [graph, setGraph] = useState<WorkflowGraph | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!domain) return;
    const controller = new AbortController();
    loadWorkflow(domain, controller.signal)
      .then((loaded) => {
        setGraph(loaded);
        setError("");
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Workflow unavailable.");
      });
    return () => controller.abort();
  }, [domain]);
  return { graph: graph?.domain === domain ? graph : null, error };
}
