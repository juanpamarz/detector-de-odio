import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export const PERIODS = [
  { days: 1, label: "24 h" },
  { days: 7, label: "7 días" },
  { days: 30, label: "30 días" },
  { days: 90, label: "90 días" },
] as const;

export type PeriodDays = (typeof PERIODS)[number]["days"];

interface PeriodState {
  days: PeriodDays;
  setDays: (d: PeriodDays) => void;
  tz: string;
}

const PeriodContext = createContext<PeriodState | null>(null);

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [days, setDays] = useState<PeriodDays>(30);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Mexico_City";
  const value = useMemo(() => ({ days, setDays, tz }), [days, tz]);
  return <PeriodContext.Provider value={value}>{children}</PeriodContext.Provider>;
}

export function usePeriod(): PeriodState {
  const ctx = useContext(PeriodContext);
  if (!ctx) throw new Error("usePeriod debe usarse dentro de PeriodProvider");
  return ctx;
}
