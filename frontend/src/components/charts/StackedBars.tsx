import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { MACROS, type ChartMacro } from "@/lib/categories";
import { num, perThousand } from "@/lib/format";
import type { StackedRow } from "@/lib/types";
import { Swatch } from "../ui";
import { TooltipCard, axisProps } from "./ChartTooltip";

/**
 * Barras horizontales apiladas por macrocategoría (orden de color fijo).
 * `kind` ajusta el pie del tooltip: advertencias para usuarios, tasa para grupos.
 */
export function StackedBars({
  data,
  kind,
  exclude = [],
  onSelect,
}: {
  data: StackedRow[];
  kind: "users" | "groups";
  exclude?: ChartMacro[];
  onSelect?: (row: StackedRow) => void;
}) {
  const series = MACROS.filter((m) => !exclude.includes(m.key));
  const height = Math.max(180, data.length * 34 + 30);

  const Tip = ({ active, payload }: TooltipProps<number, string>) => {
    const row = payload?.[0]?.payload as StackedRow | undefined;
    if (!active || !row) return null;
    const extra = row.extra;
    const footer =
      kind === "users" ? (
        <span>
          {num(Number(extra.warnings ?? 0))} advertencias acumuladas{extra.banned ? "; expulsado" : ""}
        </span>
      ) : (
        <span>
          {num(Number(extra.analyzed ?? 0))} mensajes analizados
          {typeof extra.rate === "number" && <>; {perThousand(extra.rate)} incidentes por mil</>}
        </span>
      );
    return (
      <TooltipCard
        title={row.label}
        rows={[...series.map((m) => ({ color: m.color, label: m.label, value: num(row[m.key]) })), { label: "Total", value: num(row.total) }]}
        footer={footer}
      />
    );
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
        {series.map((m) => (
          <span key={m.key} className="inline-flex items-center gap-1.5">
            <Swatch color={m.color} />
            {m.label}
          </span>
        ))}
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, left: 0, bottom: 0 }} barCategoryGap={8}>
            <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
            <XAxis type="number" allowDecimals={false} {...axisProps} />
            <YAxis
              type="category"
              dataKey="label"
              width={150}
              {...axisProps}
              tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
              tickFormatter={(v: string) => (v.length > 22 ? `${v.slice(0, 21)}…` : v)}
            />
            <Tooltip content={<Tip />} />
            {series.map((m, i) => (
              <Bar
                key={m.key}
                dataKey={m.key}
                name={m.label}
                stackId="s"
                fill={m.color}
                stroke="var(--chart-surface)"
                strokeWidth={2}
                radius={i === series.length - 1 ? [0, 4, 4, 0] : 0}
                cursor={onSelect ? "pointer" : undefined}
                onClick={(d: unknown) => onSelect?.((d as { payload: StackedRow }).payload)}
                animationDuration={650}
              >
                {i === series.length - 1 && (
                  <LabelList dataKey="total" position="right" fill="var(--chart-axis)" fontSize={11.5} />
                )}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
