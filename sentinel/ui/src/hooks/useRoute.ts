import { useCallback, useEffect, useState } from "react";
import { DOMAINS, type Domain } from "../model";

export type Route = { domain: Domain | null; recordId: string | null };

type HistoryState = { sentinelPushed?: boolean } | null;

function parseRoute(hash: string): Route {
  const [domainPart = "", recordPart = ""] = hash.replace(/^#\/?/, "").split("/");
  const domain = DOMAINS.find((candidate) => candidate === domainPart) ?? null;
  const recordId = domain && recordPart ? decodeURIComponent(recordPart) : null;
  return { domain, recordId };
}

function routeHash({ domain, recordId }: Route): string {
  if (!domain) return "#/";
  return recordId ? `#/${domain}/${encodeURIComponent(recordId)}` : `#/${domain}`;
}

export function useRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const sync = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const navigate = useCallback((next: Route, replace = false) => {
    const hash = routeHash(next);
    if (replace) window.history.replaceState(window.history.state, "", hash);
    else window.history.pushState({ sentinelPushed: true }, "", hash);
    setRoute(next);
  }, []);
  const back = useCallback(
    (fallback: Route) => {
      const state = window.history.state as HistoryState;
      if (state?.sentinelPushed) window.history.back();
      else navigate(fallback, true);
    },
    [navigate],
  );
  return { route, navigate, back };
}
