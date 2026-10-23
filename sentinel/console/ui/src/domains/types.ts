import type { ComponentType, LazyExoticComponent, ReactNode } from "react";
import type { DomainRecord } from "../model";

export type RunAction = (action: string, body?: Record<string, unknown>) => Promise<void>;

export type DetailProps = {
  record: DomainRecord;
  actions: ReactNode;
  run: RunAction;
  busy: boolean;
};

export type DomainEvent = { name: string; label: string; done: string };

export type DomainModule = {
  Detail?: LazyExoticComponent<ComponentType<DetailProps>>;
  handledActions?: string[];
  events?: DomainEvent[];
};
