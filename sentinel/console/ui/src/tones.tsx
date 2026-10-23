import { createContext, useCallback, useContext, type ReactNode } from "react";
import type { StateTone } from "./model";

const NO_TONES: Record<string, StateTone> = {};
const ToneContext = createContext<Record<string, StateTone>>(NO_TONES);

export function ToneProvider({ tones, children }: { tones: Record<string, StateTone> | undefined; children: ReactNode }) {
  return <ToneContext.Provider value={tones ?? NO_TONES}>{children}</ToneContext.Provider>;
}

export function useStateTone(): (state: string) => StateTone {
  const tones = useContext(ToneContext);
  return useCallback((state: string) => tones[state] ?? "waiting", [tones]);
}
