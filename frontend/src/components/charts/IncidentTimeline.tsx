import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { MACROS } from "@/lib/categories";
import { dateTime, hourLabel, num, perThousand, shortDate } from "@/lib/format";
import type { TimePoint } from "@/lib/types";
import { Swatch } from "../ui";
import { TooltipCard, axisProps } from "./ChartTooltip";

interface Row extends TimePoint {
  ts: number;
  rate: number | null;
}

function tickFormatter(granularity: "hour" | "day") {
  return (ts: number) => {
    const iso = new Date(ts).toISOString();
    return granularity === "hour" ? hourLabel(iso) : shortDate(iso);
  };
}

/**
 * Serie temporal apilada por macrocategoría (líneas de 2 px con área sombreada) y,
 * debajo, la tasa por cada mil mensajes en su propio eje (nunca doble eje).
 */
export function IncidentTimeline({ data, granularity }: { data: TimePoint[]; granularity: "hour" | "day" }) {
  const rows = useMemo<Row[]>(
    () => data.map((d) => ({ ...d, ts: new Date(d.bucket).getTime(), rate: d.analyzed ? (d.incidents / d.analyzed) * 1000 : null })),
    [data],
  );
  const fmt = tickFormatter(granularity);

  const Tip = ({ active, payload }: TooltipProps<number, string>) => {
    const row = payload?.[0]?.payload as Row | undefined;
    if (!active || !row) return null;
    return (
      <TooltipCard
        title={granularity === "hour" ? dateTime(row.bucket) : shortDate(row.bucket)}
        rows={[...MACROS].reverse().map((m) => ({ color: m.color, label: m.label, value: num(row[m.key]) }))}
        footer={
          <span>
            {num(row.incidents)} incidentes en {num(row.analyzed)} mensajes
            {row.rate !== null && <> ({perThousand(row.incidents / Math.max(row.analyzed, 1))} por mil)</>}
          </span>
        }
      />
    );
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
        {MACROS.map((m) => (
          <span key={m.key} className="inline-flex items-center gap-1.5">
            <Swatch color={m.color} />
            {m.label}
          </span>
        ))}
      </div>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 6, right: 8, left: -14, bottom: 0 }} syncId="timeline">
            <defs>
              {MACROS.map((m) => (
                <linearGradient key={m.key} id={`fill-${m.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={m.color} stopOpacity={0.32} />
                  <stop offset="100%" stopColor={m.color} stopOpacity={0.06} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={fmt} minTickGap={36} {...axisProps} />
            <YAxis allowDecimals={false} width={44} {...axisProps} />
            <Tooltip content={<Tip />} cursor={{ stroke: "var(--chart-axis)", strokeDasharray: "3 3" }} />
            {MACROS.map((m) => (
              <Area
                key={m.key}
                type="monotone"
                dataKey={m.key}
                name={m.label}
                stackId="1"
                stroke={m.color}
                strokeWidth={2}
                fill={`url(#fill-${m.key})`}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--chart-surface)" }}
                animationDuration={700}
                isAnimationActive
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 text-[12.5px] text-ink-2">Incidentes por cada mil mensajes analizados</div>
      <div className="h-[96px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 6, right: 8, left: -14, bottom: 0 }} syncId="timeline">
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} hide />
            <YAxis width={44} tickCount={3} {...axisProps} />
            <Tooltip content={() => null} cursor={{ stroke: "var(--chart-axis)", strokeDasharray: "3 3" }} />
            <Area type="monotone" dataKey="rate" stroke="var(--s-volume)" strokeWidth={2} fill="var(--s-volume)" fillOpacity={0.14} connectNulls dot={false} animationDuration={700} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
