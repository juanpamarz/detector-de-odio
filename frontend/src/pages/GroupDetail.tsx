import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Loader2, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Heatmap } from "@/components/charts/Heatmap";
import { PermissionBadge } from "@/components/BotPanel";
import { IncidentExplorer } from "@/components/IncidentExplorer";
import { Badge, ErrorNote, Figure, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { relative } from "@/lib/format";
import { useGroup, useHeatmap, useOverview } from "@/lib/queries";
import type { Group } from "@/lib/types";
import { DonutFigure, KpiRow, TimelineFigure, TopUsersFigure } from "./Overview";

function GroupSettings({ group }: { group: Group }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [value, setValue] = useState(group.effective_threshold);
  useEffect(() => setValue(group.effective_threshold), [group.effective_threshold]);

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Group>(`/groups/${group.id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ predicate: (q) => ["group", "groups"].includes(String(q.queryKey[0])) }),
  });
  const editable = can("admin", "moderator");
  const refresh = useMutation({
    mutationFn: () => api(`/bot/groups/${group.id}/refresh`, { method: "POST" }),
    onSettled: () => qc.invalidateQueries({ predicate: (q) => ["group", "groups"].includes(String(q.queryKey[0])) }),
  });

  return (
    <Figure title="Configuración de moderación" caption="Un umbral más bajo retira más mensajes (más sensibilidad, más falsos positivos). Por encima de 0.90 el autor ya no puede volver a publicar su mensaje.">
      <div className="space-y-5">
        <div>
          <div className="flex items-baseline justify-between text-sm">
            <span className="text-ink-2">Umbral de toxicidad</span>
            <span className="font-serif text-2xl font-semibold tabular-nums">{value.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.3}
            max={0.95}
            step={0.01}
            value={value}
            disabled={!editable}
            onChange={(e) => setValue(Number(e.target.value))}
            className="mt-2 w-full accent-[rgb(var(--brand))]"
            aria-label="Umbral de toxicidad"
          />
          <div className="mt-1 flex justify-between text-2xs text-muted">
            <span>Más estricto</span>
            <span>Más permisivo</span>
          </div>
        </div>
        {editable ? (
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary" disabled={save.isPending || value === group.effective_threshold} onClick={() => save.mutate({ toxicity_threshold: value })}>
              {save.isPending ? <Loader2 size={15} className="animate-spin" /> : save.isSuccess ? <Check size={15} /> : null}
              Guardar umbral
            </button>
            {group.toxicity_threshold !== null && (
              <button className="btn-ghost" onClick={() => save.mutate({ clear_threshold: true })}>
                Usar umbral global
              </button>
            )}
            <button className="btn-ghost" onClick={() => save.mutate({ is_active: !group.is_active })}>
              {group.is_active ? "Pausar moderación" : "Reanudar moderación"}
            </button>
          </div>
        ) : (
          <p className="text-sm text-ink-2">Tu rol permite consultar, no modificar, esta configuración.</p>
        )}
        {save.isError && <p className="text-sm text-danger">{(save.error as Error).message}</p>}
        <div className="border-t border-line pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2 text-ink-2">
              Permisos del bot <PermissionBadge status={group.bot_status} canDelete={group.can_delete} />
            </span>
            {editable && (
              <button className="btn-ghost h-8" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
                {refresh.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Verificar ahora
              </button>
            )}
          </div>
          <p className="mt-2 text-[13px] text-ink-2">
            {group.checked_at ? `Verificado ${relative(group.checked_at)}` : "Nunca verificado"}
            {group.member_count !== null ? `; ${group.member_count.toLocaleString("es-MX")} miembros` : ""}
            {group.bot_status === "administrator" || group.bot_status === "creator"
              ? `; expulsar miembros: ${group.can_restrict ? "sí" : "no"}.`
              : "."}
          </p>
          {refresh.isError && <p className="mt-1 text-sm text-danger">{(refresh.error as Error).message}</p>}
        </div>
      </div>
    </Figure>
  );
}

export default function GroupDetail() {
  const id = Number(useParams().id);
  const group = useGroup(id);
  const overview = useOverview(id);
  const heat = useHeatmap(id);

  if (group.isError) return <ErrorNote error={group.error} />;
  const g = group.data;

  return (
    <>
      <Link to="/grupos" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-ink-2 hover:text-ink">
        <ArrowLeft size={14} /> Todos los grupos
      </Link>
      {g ? (
        <PageHeader
          title={g.title}
          description={`Última actividad ${relative(g.last_activity_at)}. Identificador de Telegram ${g.id}.`}
          actions={g.is_active ? <Badge tone="good">Moderación activa</Badge> : <Badge tone="danger">Moderación en pausa</Badge>}
        />
      ) : (
        <Skeleton className="mb-8 h-16 w-1/2" />
      )}
      <KpiRow data={overview.data} />
      <div className="mt-6 grid gap-6">
        <TimelineFigure n={1} groupId={id} />
        <div className="grid gap-6 xl:grid-cols-2">
          <DonutFigure n={2} groupId={id} />
          <TopUsersFigure n={3} groupId={id} />
        </div>
        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <Figure n={4} title="Cuándo ocurren los incidentes en este grupo">
            {heat.data ? <Heatmap data={heat.data} /> : <Skeleton className="h-[200px]" />}
          </Figure>
          {g ? <GroupSettings group={g} /> : <Skeleton className="h-[260px]" />}
        </div>
        <section>
          <h2 className="mb-3 font-serif text-xl font-semibold">Registro del grupo</h2>
          <IncidentExplorer groupId={id} />
        </section>
      </div>
    </>
  );
}
