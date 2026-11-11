import { clsx } from "clsx";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <h1 className="text-[30px] font-semibold leading-tight">{title}</h1>
        {description && <p className="mt-2 text-[15px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Figura numerada al estilo de un artículo: título, cuerpo y pie explicativo. */
export function Figure({
  n,
  title,
  caption,
  actions,
  children,
  className,
}: {
  n?: number;
  title: string;
  caption?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("panel flex flex-col p-5", className)}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <h2 className="font-serif text-[17px] font-semibold leading-snug">
          {n !== undefined && <span className="mr-2 font-sans text-[13px] font-medium text-muted">Fig. {n}</span>}
          {title}
        </h2>
        {actions}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
      {caption && <p className="figure-caption mt-4 border-t border-line pt-3">{caption}</p>}
    </section>
  );
}

export function Kpi({
  label,
  value,
  hint,
  trend,
  goodWhen = "down",
}: {
  label: string;
  value: string;
  hint?: string;
  trend?: { text: string; direction: "up" | "down" | "flat" };
  goodWhen?: "up" | "down";
}) {
  const Icon = trend?.direction === "up" ? TrendingUp : trend?.direction === "down" ? TrendingDown : Minus;
  const good = trend && trend.direction !== "flat" && trend.direction === goodWhen;
  const bad = trend && trend.direction !== "flat" && trend.direction !== goodWhen;
  return (
    <div className="panel px-4 py-4">
      <div className="text-[13px] text-ink-2">{label}</div>
      <motion.div
        key={value}
        initial={{ opacity: 0.4, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="mt-1.5 font-serif text-[28px] font-semibold leading-none tracking-tight"
      >
        {value}
      </motion.div>
      {trend && (
        <div className={clsx("mt-2 flex items-center gap-1 text-xs", good && "text-good", bad && "text-danger", !good && !bad && "text-muted")}>
          <Icon size={13} aria-hidden />
          <span>{trend.text}</span>
        </div>
      )}
      {hint && !trend && <div className="mt-2 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="relative inline-flex rounded-md border border-line bg-sunken p-0.5">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={clsx("relative z-10 h-8 rounded px-3 text-[13px] transition-colors", active ? "text-ink" : "text-ink-2 hover:text-ink")}
          >
            {active && (
              <motion.span
                layoutId={`seg-${label}`}
                className="absolute inset-0 -z-10 rounded border border-line bg-panel"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function Swatch({ color, className }: { color: string; className?: string }) {
  return <span aria-hidden className={clsx("inline-block h-2.5 w-2.5 shrink-0 rounded-[3px]", className)} style={{ background: color }} />;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "danger" | "good" | "brand" }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-2xs font-medium",
        tone === "neutral" && "bg-sunken text-ink-2 ring-1 ring-inset ring-line",
        tone === "danger" && "bg-danger/10 text-danger",
        tone === "good" && "bg-good/10 text-good",
        tone === "brand" && "bg-brand/10 text-brand",
      )}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded bg-sunken", className)} />;
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex h-full min-h-[160px] flex-col items-center justify-center px-6 text-center">
      <p className="font-medium text-ink">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-ink-2">{body}</p>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "No se pudo cargar la información.";
  return <Empty title="No se pudieron cargar los datos" body={`${message} Revisa que la API esté en línea y vuelve a intentarlo.`} />;
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between gap-4 border-t border-line px-4 py-3 text-[13px] text-ink-2">
      <span>
        {from}–{to} de {total.toLocaleString("es-MX")}
      </span>
      <div className="flex items-center gap-1">
        <button className="btn-ghost h-8 px-2" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Página anterior">
          <ChevronLeft size={16} />
        </button>
        <span className="px-2">
          Página {page} de {pages}
        </span>
        <button className="btn-ghost h-8 px-2" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Página siguiente">
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
