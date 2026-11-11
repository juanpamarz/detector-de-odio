const nf = new Intl.NumberFormat("es-MX");
const nf1 = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 1 });
const dtf = new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short" });
const df = new Intl.DateTimeFormat("es-MX", { day: "numeric", month: "short" });
const hf = new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" });
const rtf = new Intl.RelativeTimeFormat("es-MX", { numeric: "auto" });

export const num = (n: number): string => nf.format(n);
export const perThousand = (rate: number): string => nf1.format(rate * 1000);
export const pct = (x: number): string => `${nf1.format(x * 100)} %`;
export const score = (x: number): string => x.toFixed(2);
export const dateTime = (iso: string): string => dtf.format(new Date(iso));
export const shortDate = (iso: string): string => df.format(new Date(iso));
export const hourLabel = (iso: string): string => hf.format(new Date(iso));

export function relative(iso: string | null): string {
  if (!iso) return "Sin actividad";
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(diff);
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export function delta(current: number, previous: number): { text: string; direction: "up" | "down" | "flat" } {
  if (previous === 0) return { text: current === 0 ? "sin cambio" : "sin referencia previa", direction: "flat" };
  const change = (current - previous) / previous;
  if (Math.abs(change) < 0.005) return { text: "sin cambio", direction: "flat" };
  return { text: `${change > 0 ? "+" : "−"}${nf1.format(Math.abs(change) * 100)} % vs. periodo previo`, direction: change > 0 ? "up" : "down" };
}
