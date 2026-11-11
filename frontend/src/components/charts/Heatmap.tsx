import { useMemo, useState } from "react";
import { scaleQuantize } from "d3-scale";
import { motion } from "framer-motion";
import { num } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { HeatCell } from "@/lib/types";

const DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const DAY_FULL = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
// Rampa secuencial de un solo tono (azul), de claro a oscuro.
const RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

/** Mapa de calor día x hora (cuándo ocurren los incidentes). */
export function Heatmap({ data }: { data: HeatCell[] }) {
  const [hover, setHover] = useState<HeatCell | null>(null);
  const { resolved } = useTheme();
  // En oscuro la rampa se invierte: lo bajo se funde con la superficie, lo alto destaca.
  const ramp = useMemo(() => (resolved === "dark" ? [...RAMP].reverse() : RAMP), [resolved]);
  const max = useMemo(() => Math.max(1, ...data.map((d) => d.count)), [data]);
  const color = useMemo(() => scaleQuantize<string>().domain([1, max]).range(ramp), [max, ramp]);
  const cell = 18;
  const gap = 2;
  const left = 34;
  const top = 18;
  const width = left + 24 * (cell + gap);
  const height = top + 7 * (cell + gap);

  return (
    <div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full min-w-[520px]" role="img" aria-label="Incidentes por día de la semana y hora">
          {[0, 6, 12, 18, 23].map((h) => (
            <text key={h} x={left + h * (cell + gap) + cell / 2} y={11} textAnchor="middle" fontSize={10} fill="var(--chart-axis)">
              {String(h).padStart(2, "0")}h
            </text>
          ))}
          {DAYS.map((d, i) => (
            <text key={d} x={0} y={top + i * (cell + gap) + cell * 0.7} fontSize={10.5} fill="var(--chart-axis)">
              {d}
            </text>
          ))}
          {data.map((c) => (
            <motion.rect
              key={`${c.weekday}-${c.hour}`}
              x={left + c.hour * (cell + gap)}
              y={top + c.weekday * (cell + gap)}
              width={cell}
              height={cell}
              rx={3}
              fill={c.count ? color(c.count) : "var(--chart-grid)"}
              initial={{ opacity: 0 }}
              animate={{ opacity: hover && (hover.weekday !== c.weekday || hover.hour !== c.hour) ? 0.55 : 1 }}
              transition={{ duration: 0.3, delay: (c.weekday * 24 + c.hour) * 0.0015 }}
              onPointerEnter={() => setHover(c)}
              onPointerLeave={() => setHover(null)}
            >
              <title>{`${DAY_FULL[c.weekday]} ${c.hour}:00: ${c.count} incidentes`}</title>
            </motion.rect>
          ))}
        </svg>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-[12.5px] text-ink-2">
        <span className="min-h-[1.25rem]">
          {hover ? `${DAY_FULL[hover.weekday]}, ${hover.hour}:00 a ${hover.hour}:59: ${num(hover.count)} incidentes` : "Pasa el cursor por una celda para ver el detalle."}
        </span>
        <span className="flex items-center gap-1.5">
          menos
          {ramp.map((c) => (
            <span key={c} className="h-2.5 w-4 rounded-sm" style={{ background: c }} />
          ))}
          más
        </span>
      </div>
    </div>
  );
}
