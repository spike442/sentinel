import { useEffect, useState } from "react";

export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, refreshKey: number, initial: T, unavailable: string) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal)
      .then((loaded) => {
        setValue(loaded);
        setError("");
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : unavailable);
      });
    return () => controller.abort();
  }, [load, refreshKey, unavailable]);
  return { value, error };
}
