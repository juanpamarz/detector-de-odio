import { useMemo, useState } from "react";
import { arc as d3arc } from "d3-shape";
import { AnimatePresence, motion } from "framer-motion";
import { CATEGORY_LABEL, MACROS, type ChartMacro } from "@/lib/categories";
import { num, pct } from "@/lib/format";
import type { CategorySlice, HateCategory } from "@/lib/types";
import { Swatch } from "../ui";

interface Seg {
  key: string;
  label: string;
  count: number;
  start: number;
  end: number;
  color: string;
  opacity: number;
  ring: "inner" | "outer";
  macro: ChartMacro;
}

const SIZE = 280;
const R = { innerIn: 64, innerOut: 94, outerIn: 98, outerOut: 128 };
const TAU = Math.PI * 2;

/**
 * Dona multicapa construida con d3-shape.
 * Anillo interior: macrocategoría. Anillo exterior: subcategorías dentro del mismo
 * arco angular de su macrocategoría (mismo tono, distinta intensidad).
 */
export function NestedDonut({ data }: { data: CategorySlice[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = data.reduce((a, d) => a + d.count, 0);

  const segments = useMemo<Seg[]>(() => {
    const out: Seg[] = [];
    let angle = 0;
    for (const m of MACROS) {
      const items = data.filter((d) => d.macro === m.key).sort((a, b) => b.count - a.count);
      const macroTotal = items.reduce((a, d) => a + d.count, 0);
      if (!macroTotal) continue;
      const span = (macroTotal / total) * TAU;
      out.push({ key: m.key, label: m.label, count: macroTotal, start: angle, end: angle + span, color: m.color, opacity: 1, ring: "inner", macro: m.key });
      let sub = angle;
      items.forEach((it, i) => {
        const s = (it.count / total) * TAU;
        out.push({
          key: `${m.key}:${it.category}`,
          label: CATEGORY_LABEL[it.category as HateCategory],
          count: it.count,
          start: sub,
          end: sub + s,
          color: m.color,
          opacity: Math.max(0.38, 0.92 - i * 0.16),
          ring: "outer",
          macro: m.key,
        });
        sub += s;
      });
      angle += span;
    }
    return out;
  }, [data, total]);

  const arcGen = d3arc<Seg>()
    .innerRadius((d) => (d.ring === "inner" ? R.innerIn : R.outerIn))
    .outerRadius((d) => (d.ring === "inner" ? R.innerOut : R.outerOut))
    .startAngle((d) => d.start)
    .endAngle((d) => d.end)
    .padAngle(0.008)
    .cornerRadius(2);

  const active = segments.find((s) => s.key === hover);
  const macroTotals = MACROS.map((m) => ({ ...m, count: segments.find((s) => s.ring === "inner" && s.key === m.key)?.count ?? 0 }));

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center sm:gap-8">
      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        <svg viewBox={`${-SIZE / 2} ${-SIZE / 2} ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} role="img" aria-label="Distribución de incidentes por categoría">
          {segments.map((s, i) => {
            const dim = hover !== null && hover !== s.key && !(active?.ring === "inner" && s.macro === active.macro);
            return (
              <motion.path
                key={s.key}
                d={arcGen(s) ?? undefined}
                fill={s.color}
                stroke="var(--chart-surface)"
                strokeWidth={2}
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: dim ? 0.18 : s.opacity, scale: hover === s.key ? 1.025 : 1 }}
                transition={{ duration: 0.45, delay: i * 0.015, ease: [0.22, 1, 0.36, 1] }}
                onPointerEnter={() => setHover(s.key)}
                onPointerLeave={() => setHover(null)}
                className="cursor-pointer"
              >
                <title>{`${s.label}: ${num(s.count)} (${pct(s.count / total)})`}</title>
              </motion.path>
            );
          })}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <AnimatePresence mode="wait">
            <motion.div key={active?.key ?? "total"} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18 }}>
              <div className="font-serif text-[26px] font-semibold leading-none">{num(active?.count ?? total)}</div>
              <div className="mx-auto mt-1.5 max-w-[104px] text-[12px] leading-tight text-ink-2">
                {active ? `${active.label}, ${pct(active.count / total)}` : "incidentes"}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <ul className="w-full min-w-0 space-y-3 text-[13px]">
        {macroTotals.map((m) => (
          <li key={m.key} onPointerEnter={() => setHover(m.key)} onPointerLeave={() => setHover(null)} className="cursor-default">
            <div className="flex items-center gap-2">
              <Swatch color={m.color} />
              <span className="flex-1 text-ink">{m.label}</span>
              <span className="tabular-nums text-ink">{num(m.count)}</span>
              <span className="w-14 text-right tabular-nums text-muted">{total ? pct(m.count / total) : "—"}</span>
            </div>
            <ul className="ml-[18px] mt-1 space-y-0.5 text-ink-2">
              {segments
                .filter((s) => s.ring === "outer" && s.macro === m.key)
                .map((s) => (
                  <li key={s.key} className="flex justify-between gap-2" onPointerEnter={() => setHover(s.key)}>
                    <span className="truncate">{s.label}</span>
                    <span className="tabular-nums">{num(s.count)}</span>
                  </li>
                ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
