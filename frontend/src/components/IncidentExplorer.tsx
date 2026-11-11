import { useEffect, useMemo, useState } from "react";
import { clsx } from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { FileDown, FileText, Loader2, RotateCcw, Search, X } from "lucide-react";
import { download, type Params } from "@/lib/api";
import { ACTION_LABEL, CATEGORY_LABEL, MACROS, MACRO_COLOR, type ChartMacro } from "@/lib/categories";
import { dateTime, score } from "@/lib/format";
import { usePeriod } from "@/lib/period";
import { useGroups, useIncidents } from "@/lib/queries";
import type { ActionTaken, Incident } from "@/lib/types";
import { Badge, Empty, ErrorNote, Pagination, Skeleton, Swatch } from "./ui";

interface FilterState {
  q: string;
  macros: ChartMacro[];
  action: ActionTaken | "";
  minScore: number;
  dateFrom: string;
  dateTo: string;
  groupId: string;
  sort: "-created_at" | "-toxicity_score" | "created_at";
}

const EMPTY: FilterState = { q: "", macros: [], action: "", minScore: 0, dateFrom: "", dateTo: "", groupId: "", sort: "-created_at" };

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function ScoreBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-sunken">
        <div className="h-full rounded-full bg-ink-2" style={{ width: `${value * 100}%` }} />
      </div>
      <span className="tabular-nums text-ink-2">{score(value)}</span>
    </div>
  );
}

export function IncidentExplorer({ groupId }: { groupId?: number }) {
  const { tz } = usePeriod();
  const [f, setF] = useState<FilterState>(EMPTY);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);
  const q = useDebounced(f.q);
  const groups = useGroups();

  const params: Params = useMemo(
    () => ({
      q,
      macro: f.macros,
      action: f.action || undefined,
      min_score: f.minScore > 0 ? f.minScore : undefined,
      date_from: f.dateFrom ? new Date(`${f.dateFrom}T00:00:00`).toISOString() : undefined,
      date_to: f.dateTo ? new Date(`${f.dateTo}T23:59:59`).toISOString() : undefined,
      group_id: groupId ?? (f.groupId || undefined),
      sort: f.sort,
    }),
    [q, f.macros, f.action, f.minScore, f.dateFrom, f.dateTo, f.groupId, f.sort, groupId],
  );

  useEffect(() => setPage(1), [params]);
  const list = useIncidents({ ...params, page, page_size: pageSize });
  const set = <K extends keyof FilterState>(k: K, v: FilterState[K]) => setF((prev) => ({ ...prev, [k]: v }));
  const dirty = JSON.stringify(f) !== JSON.stringify(EMPTY);

  async function exportAs(kind: "csv" | "pdf") {
    setExporting(kind);
    try {
      await download(`/exports/incidents.${kind}`, { ...params, tz }, `incidentes.${kind}`);
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="panel overflow-hidden">
      {/* Filtros en una sola franja sobre la tabla */}
      <div className="space-y-3 border-b border-line p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className="input pl-9" placeholder="Buscar en mensajes o personas" value={f.q} onChange={(e) => set("q", e.target.value)} aria-label="Buscar" />
          </div>
          {groupId === undefined && (
            <select className="input w-auto max-w-[220px]" value={f.groupId} onChange={(e) => set("groupId", e.target.value)} aria-label="Grupo">
              <option value="">Todos los grupos</option>
              {groups.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title}
                </option>
              ))}
            </select>
          )}
          <select className="input w-auto" value={f.action} onChange={(e) => set("action", e.target.value as ActionTaken | "")} aria-label="Acción">
            <option value="">Cualquier acción</option>
            {(Object.keys(ACTION_LABEL) as ActionTaken[]).map((a) => (
              <option key={a} value={a}>
                {ACTION_LABEL[a]}
              </option>
            ))}
          </select>
          <select className="input w-auto" value={f.sort} onChange={(e) => set("sort", e.target.value as FilterState["sort"])} aria-label="Orden">
            <option value="-created_at">Más recientes</option>
            <option value="created_at">Más antiguos</option>
            <option value="-toxicity_score">Mayor toxicidad</option>
          </select>
          <div className="ml-auto flex gap-2">
            <button className="btn-ghost" onClick={() => exportAs("csv")} disabled={exporting !== null}>
              {exporting === "csv" ? <Loader2 size={15} className="animate-spin" /> : <FileDown size={15} />}
              CSV
            </button>
            <button className="btn-ghost" onClick={() => exportAs("pdf")} disabled={exporting !== null}>
              {exporting === "pdf" ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}
              PDF
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px]">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Macrocategorías">
            {MACROS.map((m) => {
              const on = f.macros.includes(m.key);
              return (
                <button
                  key={m.key}
                  aria-pressed={on}
                  onClick={() => set("macros", on ? f.macros.filter((x) => x !== m.key) : [...f.macros, m.key])}
                  className={clsx("inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 transition-colors", on ? "border-ink/30 bg-sunken text-ink" : "border-line text-ink-2 hover:text-ink")}
                >
                  <Swatch color={m.color} />
                  {m.label}
                </button>
              );
            })}
          </div>
          <label className="flex items-center gap-2 text-ink-2">
            Toxicidad mínima
            <input type="range" min={0} max={1} step={0.05} value={f.minScore} onChange={(e) => set("minScore", Number(e.target.value))} className="w-28 accent-[rgb(var(--brand))]" />
            <span className="w-8 tabular-nums text-ink">{f.minScore.toFixed(2)}</span>
          </label>
          <label className="flex items-center gap-2 text-ink-2">
            Desde
            <input type="date" className="input h-8 w-auto" value={f.dateFrom} onChange={(e) => set("dateFrom", e.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-ink-2">
            Hasta
            <input type="date" className="input h-8 w-auto" value={f.dateTo} onChange={(e) => set("dateTo", e.target.value)} />
          </label>
          {dirty && (
            <button className="inline-flex items-center gap-1 text-ink-2 hover:text-ink" onClick={() => setF(EMPTY)}>
              <RotateCcw size={13} /> Limpiar filtros
            </button>
          )}
        </div>
      </div>

      {list.isError ? (
        <ErrorNote error={list.error} />
      ) : !list.data ? (
        <div className="space-y-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
      ) : list.data.items.length === 0 ? (
        <Empty title="Ningún incidente coincide" body="Ajusta o limpia los filtros para ampliar la búsqueda." />
      ) : (
        <div className={clsx("overflow-x-auto transition-opacity", list.isFetching && "opacity-70")}>
          <table className="w-full min-w-[960px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[12.5px] text-ink-2">
                <th className="px-4 py-2.5 font-medium">Fecha</th>
                {groupId === undefined && <th className="px-4 py-2.5 font-medium">Grupo</th>}
                <th className="px-4 py-2.5 font-medium">Persona</th>
                <th className="px-4 py-2.5 font-medium">Categoría</th>
                <th className="px-4 py-2.5 font-medium">Mensaje</th>
                <th className="px-4 py-2.5 font-medium">Toxicidad</th>
                <th className="px-4 py-2.5 font-medium">Acción</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((i) => (
                <tr key={i.id} onClick={() => setSelected(i)} className="cursor-pointer border-b border-line last:border-0 hover:bg-sunken">
                  <td className="whitespace-nowrap px-4 py-2.5 text-ink-2">{dateTime(i.created_at)}</td>
                  {groupId === undefined && <td className="max-w-[180px] truncate px-4 py-2.5">{i.group_title}</td>}
                  <td className="px-4 py-2.5">{i.user_display}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span className="inline-flex items-center gap-1.5">
                      <Swatch color={MACRO_COLOR[i.macro_category]} />
                      {CATEGORY_LABEL[i.category]}
                    </span>
                  </td>
                  <td className={clsx("max-w-[340px] truncate px-4 py-2.5", i.is_text_redacted && "italic text-muted")}>{i.message_text}</td>
                  <td className="px-4 py-2.5">{i.macro_category === "crisis" ? <span className="text-muted">—</span> : <ScoreBar value={i.toxicity_score} />}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <Badge tone={i.action === "deleted_banned" ? "danger" : i.action === "deleted_crisis_support" ? "brand" : "neutral"}>{ACTION_LABEL[i.action]}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list.data && (
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 pl-4 text-[13px] text-ink-2">
            Filas
            <select className="input h-8 w-auto" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>
              {[10, 25, 50, 100].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
          <div className="flex-1">
            <Pagination page={page} pageSize={pageSize} total={list.data.total} onPage={setPage} />
          </div>
        </div>
      )}

      <IncidentDrawer incident={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function IncidentDrawer({ incident, onClose }: { incident: Incident | null; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <AnimatePresence>
      {incident && (
        <>
          <motion.div className="fixed inset-0 z-40 bg-black/30" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside
            role="dialog"
            aria-label={`Incidente ${incident.id}`}
            className="fixed inset-y-0 right-0 z-50 w-full max-w-md overflow-y-auto border-l border-line bg-panel p-6"
            initial={{ x: 480 }}
            animate={{ x: 0 }}
            exit={{ x: 480 }}
            transition={{ type: "spring", stiffness: 360, damping: 38 }}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[13px] text-muted">Incidente {incident.id}</div>
                <h3 className="mt-1 text-xl font-semibold">{CATEGORY_LABEL[incident.category]}</h3>
              </div>
              <button className="btn-ghost h-8 px-2" onClick={onClose} aria-label="Cerrar">
                <X size={16} />
              </button>
            </div>
            <blockquote className={clsx("mt-5 rounded-md border-l-2 bg-sunken px-4 py-3 text-[15px] leading-relaxed", incident.is_text_redacted && "italic text-muted")} style={{ borderColor: MACRO_COLOR[incident.macro_category] }}>
              {incident.message_text}
            </blockquote>
            <dl className="mt-6 grid grid-cols-[130px_1fr] gap-y-2.5 text-sm">
              <dt className="text-ink-2">Grupo</dt>
              <dd>{incident.group_title}</dd>
              <dt className="text-ink-2">Persona</dt>
              <dd>
                {incident.user_display} <span className="text-muted">({incident.user_id})</span>
              </dd>
              <dt className="text-ink-2">Enviado</dt>
              <dd>{dateTime(incident.message_sent_at)}</dd>
              <dt className="text-ink-2">Toxicidad</dt>
              <dd className="tabular-nums">{score(incident.toxicity_score)}</dd>
              <dt className="text-ink-2">Riesgo de crisis</dt>
              <dd className="tabular-nums">{score(incident.crisis_score)}</dd>
              <dt className="text-ink-2">Acción</dt>
              <dd>{ACTION_LABEL[incident.action]}</dd>
              <dt className="text-ink-2">Respuesta</dt>
              <dd>{incident.user_response === "withdrawn" ? "Retiró el mensaje" : incident.user_response === "republished" ? "Lo publicó de todos modos" : "Sin respuesta"}</dd>
            </dl>
            <h4 className="mt-7 font-serif text-[15px] font-semibold">Veredicto por modelo</h4>
            <ul className="mt-2 divide-y divide-line rounded-md border border-line text-sm">
              {incident.providers.map((p) => (
                <li key={p.name} className="flex items-center justify-between gap-3 px-3 py-2">
                  <span>{p.name}</span>
                  {p.error ? (
                    <span className="truncate text-xs text-danger" title={p.error}>
                      sin respuesta
                    </span>
                  ) : (
                    <span className="tabular-nums text-ink-2">
                      {p.toxicity !== undefined ? `tox. ${score(p.toxicity)}` : ""}
                      {p.latency_ms !== undefined ? `, ${Math.round(p.latency_ms)} ms` : ""}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
