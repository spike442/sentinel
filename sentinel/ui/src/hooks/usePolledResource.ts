import { useEffect, useRef, useState } from "react";

const POLL_INTERVAL_MS = 5000;

export function usePolledResource<T>(
  enabled: boolean,
  refreshKey: number,
  load: (signal: AbortSignal) => Promise<T>,
  initial: T,
  unavailable: string,
) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState("");
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let inFlight = false;
    async function poll() {
      window.clearTimeout(timer);
      if (inFlight || document.hidden) return;
      inFlight = true;
      try {
        const loaded = await loader.current(controller.signal);
        if (controller.signal.aborted) return;
        setValue(loaded);
        setError("");
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : unavailable);
      } finally {
        inFlight = false;
        if (!controller.signal.aborted) timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
      }
    }
    const resume = () => void poll();
    document.addEventListener("visibilitychange", resume);
    void poll();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", resume);
    };
  }, [enabled, refreshKey, unavailable]);
  return { value, error };
}
