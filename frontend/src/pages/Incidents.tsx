import { IncidentExplorer } from "@/components/IncidentExplorer";
import { PageHeader } from "@/components/ui";

export default function Incidents() {
  return (
    <>
      <PageHeader
        title="Incidentes"
        description="Registro auditable de cada mensaje retirado. Filtra por categoría, grupo, fecha o puntaje y exporta exactamente lo que ves a CSV o PDF."
      />
      <IncidentExplorer />
    </>
  );
}
