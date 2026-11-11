import type { ReactNode } from "react";
import { Swatch } from "../ui";

export interface TipRow {
  color?: string;
  label: string;
  value: string;
}

export function TooltipCard({ title, rows, footer }: { title: string; rows: TipRow[]; footer?: ReactNode }) {
  return (
    <div className="min-w-[180px] rounded-md border border-line bg-panel px-3 py-2.5 text-[12.5px] shadow-[0_6px_24px_-12px_rgb(0_0_0/0.35)]">
      <div className="mb-1.5 font-medium text-ink">{title}</div>
      <ul className="space-y-1">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-2">
            {r.color && <Swatch color={r.color} />}
            <span className="flex-1 text-ink-2">{r.label}</span>
            <span className="tabular-nums text-ink">{r.value}</span>
          </li>
        ))}
      </ul>
      {footer && <div className="mt-2 border-t border-line pt-1.5 text-ink-2">{footer}</div>}
    </div>
  );
}

export const axisProps = {
  stroke: "var(--chart-axis)",
  tick: { fill: "var(--chart-axis)", fontSize: 11.5 },
  tickLine: false,
  axisLine: false,
} as const;
