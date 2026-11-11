import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Heatmap } from "@/components/charts/Heatmap";
import { IncidentTimeline } from "@/components/charts/IncidentTimeline";
import { NestedDonut } from "@/components/charts/NestedDonut";
import { StackedBars } from "@/components/charts/StackedBars";
import { Empty, ErrorNote, Figure, Kpi, PageHeader, Segmented, Skeleton } from "@/components/ui";
import { delta, num, pct, perThousand } from "@/lib/format";
import { usePeriod } from "@/lib/period";
import { useDistribution, useGroupRanking, useHeatmap, useOverview, useTimeseries, useTopUsers } from "@/lib/queries";
import type { Overview as OverviewT } from "@/lib/types";

export function KpiRow({ data }: { data: OverviewT | undefined }) {
  if (!data) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-[104px]" />
        ))}
      </div>
    );
  }
  const answered = data.withdrawn + data.republished;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Kpi label="Mensajes analizados" value={num(data.analyzed)} hint={`${num(data.active_groups)} grupos con actividad`} />
      <Kpi label="Incidentes" value={num(data.incidents)} trend={delta(data.incidents, data.incidents_prev)} goodWhen="down" />
      <Kpi label="Incidentes por mil mensajes" value={perThousand(data.incident_rate)} hint={`Toxicidad media ${data.mean_toxicity.toFixed(2)}`} />
      <Kpi label="Alertas de crisis" value={num(data.crisis)} hint="Apoyo enviado en privado" />
      <Kpi label="Personas sancionadas" value={num(data.users_sanctioned)} hint={`${num(data.users_banned)} expulsadas en total`} />
      <Kpi
        label="Reconsideración"
        value={answered ? pct(data.withdrawn / answered) : "—"}
        hint={answered ? `${num(data.withdrawn)} retiraron, ${num(data.republished)} insistieron` : "Sin respuestas al aviso"}
      />
    </div>
  );
}

export function TimelineFigure({ n, groupId }: { n: number; groupId?: number }) {
  const { days } = usePeriod();
  const [gran, setGran] = useState<"hour" | "day">(days <= 7 ? "hour" : "day");
  const effective = days > 14 ? "day" : gran;
  const q = useTimeseries(effective, groupId);
  const total = q.data?.reduce((a, p) => a + p.incidents, 0) ?? 0;
  return (
    <Figure
      n={n}
      title="Evolución de incidentes"
      actions={
        days <= 14 ? (
          <Segmented label="Granularidad" value={effective} onChange={setGran} options={[{ value: "hour", label: "Por hora" }, { value: "day", label: "Por día" }] as const} />
        ) : undefined
      }
      caption="Áreas apiladas por macrocategoría. La franja inferior normaliza por volumen: un pico de incidentes con tasa estable refleja más conversación, no más hostilidad."
    >
      {q.isError ? <ErrorNote error={q.error} /> : !q.data ? <Skeleton className="h-[380px]" /> : total === 0 ? <Empty title="Sin incidentes en este periodo" body="Cuando el bot retire un mensaje aparecerá aquí." /> : <IncidentTimeline data={q.data} granularity={effective} />}
    </Figure>
  );
}

export function DonutFigure({ n, groupId }: { n: number; groupId?: number }) {
  const q = useDistribution(groupId);
  return (
    <Figure n={n} title="Distribución por categoría de daño" caption="Anillo interior: macrocategoría. Anillo exterior: subcategoría dentro del mismo arco. Las alertas de crisis no son sanciones; se muestran para dimensionar la necesidad de apoyo.">
      {q.isError ? <ErrorNote error={q.error} /> : !q.data ? <Skeleton className="h-[280px]" /> : q.data.length === 0 ? <Empty title="Sin datos" body="Aún no hay incidentes clasificados en este periodo." /> : <NestedDonut data={q.data} />}
    </Figure>
  );
}

export function TopUsersFigure({ n, groupId }: { n: number; groupId?: number }) {
  const q = useTopUsers(groupId);
  return (
    <Figure n={n} title="Personas con más sanciones" caption="Incidentes sancionables por persona (excluye alertas de crisis). El detalle muestra advertencias acumuladas y expulsiones.">
      {q.isError ? <ErrorNote error={q.error} /> : !q.data ? <Skeleton className="h-[300px]" /> : q.data.length === 0 ? <Empty title="Nadie ha sido sancionado" body="No hay incidentes sancionables en el periodo elegido." /> : <StackedBars data={q.data} kind="users" exclude={["crisis"]} />}
    </Figure>
  );
}

export default function Overview() {
  const navigate = useNavigate();
  const overview = useOverview();
  const ranking = useGroupRanking();
  const heat = useHeatmap();

  return (
    <>
      <PageHeader title="Panorama" description="Estado de la convivencia en todos los grupos donde opera el bot. Los datos se actualizan cada 30 segundos." />
      <KpiRow data={overview.data} />

      <div className="mt-6 grid gap-6">
        <TimelineFigure n={1} />
        <div className="grid gap-6 xl:grid-cols-2">
          <DonutFigure n={2} />
          <TopUsersFigure n={3} />
        </div>
        <div className="grid gap-6 xl:grid-cols-2">
          <Figure n={4} title="Grupos más expuestos" caption="Incidentes por grupo, apilados por macrocategoría. Selecciona una barra para abrir el grupo.">
            {ranking.isError ? (
              <ErrorNote error={ranking.error} />
            ) : !ranking.data ? (
              <Skeleton className="h-[300px]" />
            ) : ranking.data.length === 0 ? (
              <Empty title="Sin grupos con incidentes" body="Agrega el bot a un grupo como administrador para empezar." />
            ) : (
              <StackedBars data={ranking.data} kind="groups" onSelect={(r) => navigate(`/grupos/${r.id}`)} />
            )}
          </Figure>
          <Figure n={5} title="Cuándo ocurren los incidentes" caption="Conteo por día de la semana y hora local. Útil para programar moderación humana en las franjas de mayor riesgo.">
            {heat.isError ? <ErrorNote error={heat.error} /> : !heat.data ? <Skeleton className="h-[220px]" /> : <Heatmap data={heat.data} />}
          </Figure>
        </div>
      </div>
    </>
  );
}
