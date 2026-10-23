import { lazy } from "react";
import type { DomainModule } from "./types";

export const WORKFLOW_MODULES: Record<string, DomainModule> = {
  "sre/incidents": {
    Detail: lazy(() => import("./sre/incidents/IncidentDetail")),
    handledActions: ["manual-action"],
  },
  "sre/reviews": {
    Detail: lazy(() => import("./sre/reviews/ReviewDetail")),
    events: [{ name: "check", label: "Check now", done: "Pull request discovery queued." }],
  },
};

export function workflowModule(domain: string, workflow: string): DomainModule {
  return WORKFLOW_MODULES[`${domain}/${workflow}`] ?? {};
}
