import { useCallback, useEffect, useState } from "react";

export type Route = { domain: string | null; view: string | null; recordId: string | null };

type HistoryState = { sentinelPushed?: boolean } | null;

function part(value: string | undefined): string | null {
  return value ? decodeURIComponent(value) : null;
}

function parseRoute(hash: string): Route {
  const [domain, view, recordId] = hash.replace(/^#\/?/, "").split("/").map(part);
  return { domain: domain ?? null, view: domain ? (view ?? null) : null, recordId: view ? (recordId ?? null) : null };
}

export function routeHash({ domain, view, recordId }: Route): string {
  const parts = [domain, domain && view, domain && view && recordId].filter((value): value is string => Boolean(value));
  return `#/${parts.map(encodeURIComponent).join("/")}`;
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
