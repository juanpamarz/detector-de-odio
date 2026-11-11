import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUpRight, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { BotPanel, PermissionBadge } from "@/components/BotPanel";
import { Badge, Empty, ErrorNote, PageHeader, Skeleton } from "@/components/ui";
import { num, perThousand, relative } from "@/lib/format";
import { useGroups } from "@/lib/queries";
import type { Group } from "@/lib/types";

type SortKey = "incidents" | "incident_rate" | "analyzed" | "title";

export default function Groups() {
  const q = useGroups();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("incidents");

  const rows = useMemo(() => {
    const list = (q.data ?? []).filter((g) => g.title.toLowerCase().includes(search.toLowerCase()));
    return [...list].sort((a, b) => (sort === "title" ? a.title.localeCompare(b.title) : (b[sort] as number) - (a[sort] as number)));
  }, [q.data, search, sort]);

  const maxRate = Math.max(0.0001, ...rows.map((g) => g.incident_rate));

  return (
    <>
      <PageHeader title="Grupos" description="Cada grupo de Telegram donde el bot es administrador. Abre uno para ver sus métricas, ajustar su umbral y exportar sus reportes." />
      <BotPanel />
      <div className="panel overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div className="relative w-full max-w-xs">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className="input pl-9" placeholder="Buscar grupo" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Buscar grupo" />
          </div>
          <label className="ml-auto flex items-center gap-2 text-[13px] text-ink-2">
            Ordenar por
            <select className="input h-9 w-auto" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
              <option value="incidents">Incidentes</option>
              <option value="incident_rate">Tasa por mil</option>
              <option value="analyzed">Mensajes analizados</option>
              <option value="title">Nombre</option>
            </select>
          </label>
        </div>

        {q.isError ? (
          <ErrorNote error={q.error} />
        ) : !q.data ? (
          <div className="space-y-2 p-4">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : rows.length === 0 ? (
          <Empty title="Aún no hay grupos registrados" body="Escribe /registrar dentro del grupo o agrégalo arriba con su ID. El bot necesita ser administrador con permiso de borrar mensajes." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[12.5px] text-ink-2">
                  <th className="px-4 py-2.5 font-medium">Grupo</th>
                  <th className="px-4 py-2.5 font-medium">Bot</th>
                  <th className="px-4 py-2.5 text-right font-medium">Mensajes</th>
                  <th className="px-4 py-2.5 text-right font-medium">Incidentes</th>
                  <th className="w-[200px] px-4 py-2.5 font-medium">Por mil mensajes</th>
                  <th className="px-4 py-2.5 text-right font-medium">Crisis</th>
                  <th className="px-4 py-2.5 text-right font-medium">Expulsiones</th>
                  <th className="px-4 py-2.5 font-medium">Umbral</th>
                  <th className="px-4 py-2.5 font-medium">Última actividad</th>
                  <th className="px-2 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {rows.map((g: Group, i) => (
                  <motion.tr
                    key={g.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="group border-b border-line last:border-0 hover:bg-sunken"
                  >
                    <td className="px-4 py-3">
                      <Link to={`/grupos/${g.id}`} className="font-medium text-ink hover:underline">
                        {g.title}
                      </Link>
                      <div className="mt-0.5 flex items-center gap-2 text-2xs text-muted">
                        <span>ID {g.id}</span>
                        {!g.is_active && <Badge tone="danger">En pausa</Badge>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <PermissionBadge status={g.bot_status} canDelete={g.can_delete} />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{num(g.analyzed)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{num(g.incidents)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
                          <motion.div className="h-full rounded-full bg-[var(--s-identity)]" initial={{ width: 0 }} animate={{ width: `${(g.incident_rate / maxRate) * 100}%` }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} />
                        </div>
                        <span className="w-10 text-right tabular-nums text-ink-2">{perThousand(g.incident_rate)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{num(g.crisis)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{num(g.banned)}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {g.effective_threshold.toFixed(2)} {g.toxicity_threshold !== null && <Badge tone="brand">propio</Badge>}
                    </td>
                    <td className="px-4 py-3 text-ink-2">{relative(g.last_activity_at)}</td>
                    <td className="px-2 py-3">
                      <Link to={`/grupos/${g.id}`} className="flex h-8 w-8 items-center justify-center rounded text-muted opacity-0 transition-opacity hover:text-ink group-hover:opacity-100" aria-label={`Abrir ${g.title}`}>
                        <ArrowUpRight size={16} />
                      </Link>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
