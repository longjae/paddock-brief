"use client";

import { createContext, useContext, useState } from "react";
import type { EventDetail, EventSummary } from "@/lib/types";

type Cached<T> = { data: T; savedAt: number };
type DashboardCache = {
  events: Map<string, Cached<EventDetail>>;
  calendars: Map<number, Cached<EventSummary[]>>;
  lastEvent: Cached<EventDetail> | null;
};

const DashboardCacheContext = createContext<DashboardCache | null>(null);

export function DashboardCacheProvider({ children }: { children: React.ReactNode }) {
  const [cache] = useState<DashboardCache>(() => ({ events: new Map(), calendars: new Map(), lastEvent: null }));
  return <DashboardCacheContext.Provider value={cache}>{children}</DashboardCacheContext.Provider>;
}

export function useDashboardCache() {
  const cache = useContext(DashboardCacheContext);
  if (!cache) throw new Error("DashboardCacheProvider is required");
  return cache;
}
