import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { Badge, Figure, PageHeader, Swatch } from "@/components/ui";
import { api } from "@/lib/api";
import { CATEGORY_LABEL, CATEGORY_MACRO, MACRO_COLOR } from "@/lib/categories";
import { score } from "@/lib/format";
import { useGroups } from "@/lib/queries";
import type { HateCategory, MacroCategory } from "@/lib/types";

interface ProviderResult {
  name: string;
  toxicity: number | null;
  crisis: number | null;
  latency_ms: number | null;
  rationale: string | null;
  top_category: HateCategory | null;
  error: string | null;
}

interface TestResult {
  verdict: "allow" | "crisis_support" | "delete_and_warn";
  toxicity: number;
  crisis: number;
  identity: number;
  category: HateCategory;
  macro: MacroCategory;
  category_scores: Partial<Record<HateCategory, number>>;
  thresholds: { toxicity: number; identity: number; crisis: number; hard_block: number };
  providers: ProviderResult[];
  safety_net: string | null;
}

const VERDICT = {
  allow: { label: "Se permitiría", tone: "good" as const, body: "Ningún puntaje alcanza su umbral; el mensaje se quedaría en el grupo." },
  delete_and_warn: { label: "Se borraría", tone: "danger" as const, body: "El bot retiraría el mensaje, sumaría una advertencia y enviaría el aviso de reflexión." },
  crisis_support: { label: "Apoyo en crisis", tone: "brand" as const, body: "El bot retiraría el mensaje por privacidad y enviaría apoyo en privado." },
};

const PROVIDER_LABEL: Record<string, string> = {
  groq: "Groq",
  cerebras: "Cerebras",
  openrouter: "OpenRouter",
  edenai: "Eden AI",
  heuristic: "Reglas léxicas",
};

function Meter({ label, value, threshold }: { label: string; value: number; threshold: number }) {
  const over = value >= threshold;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-[13px]">
        <span className="text-ink-2">{label}</span>
        <span className="tabular-nums">
          <span className={over ? "font-semibold text-danger" : "text-ink"}>{score(value)}</span>
          <span className="text-muted"> / umbral {score(threshold)}</span>
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-sunken">
        <motion.div className={`h-full rounded-full ${over ? "bg-danger" : "bg-ink-2"}`} initial={{ width: 0 }} animate={{ width: `${value * 100}%` }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} />
        <div className="absolute -top-1 h-4 w-0.5 rounded bg-ink" style={{ left: `${threshold * 100}%` }} aria-hidden />
      </div>
    </div>
  );
}

export default function Lab() {
  const groups = useGroups();
  const [text, setText] = useState("");
  const [groupId, setGroupId] = useState("");
  const run = useMutation({
    mutationFn: () => api<TestResult>("/moderation/test", { method: "POST", body: JSON.stringify({ text, group_id: groupId ? Number(groupId) : null }) }),
  });
  const analyze = () => {
    if (text.trim() && !run.isPending) run.mutate();
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    analyze();
  };
  const r = run.data;
  const v = r ? VERDICT[r.verdict] : null;
  const cats = r ? (Object.entries(r.category_scores) as [HateCategory, number][]).filter(([c]) => c !== "self_harm").slice(0, 6) : [];

  return (
    <>
      <PageHeader
        title="Probar mensajes"
        description="Escribe un mensaje para ver cómo lo clasificaría el bot, con el puntaje de cada modelo. No se publica ni se guarda: sirve para calibrar umbrales y explicar las decisiones."
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_1.15fr]">
        <Figure title="Mensaje">
          <form onSubmit={submit} className="space-y-3">
            <textarea
              className="input h-36 resize-y py-2.5 leading-relaxed"
              placeholder="Escribe o pega un mensaje del grupo"
              value={text}
              maxLength={2000}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) analyze();
              }}
            />
            <div className="flex flex-wrap items-center gap-2">
              <select className="input w-auto max-w-[260px]" value={groupId} onChange={(e) => setGroupId(e.target.value)} aria-label="Umbral del grupo">
                <option value="">Umbral global</option>
                {groups.data?.map((g) => (
                  <option key={g.id} value={g.id}>
                    Umbral de {g.title}
                  </option>
                ))}
              </select>
              <button className="btn-primary ml-auto" disabled={run.isPending || !text.trim()}>
                {run.isPending && <Loader2 size={15} className="animate-spin" />}
                {run.isPending ? "Analizando" : "Analizar"}
              </button>
            </div>
            <p className="text-[12.5px] text-muted">Ctrl + Enter para analizar.</p>
            {run.isError && <p className="text-sm text-danger">{(run.error as Error).message}</p>}
          </form>
        </Figure>

        <AnimatePresence mode="wait">
          {r && v ? (
            <motion.div key={r.toxicity + r.category + text.length} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <Figure title="Decisión" actions={<Badge tone={v.tone}>{v.label}</Badge>}>
                <p className="text-sm text-ink-2">{v.body}</p>
                {r.category !== "none" && (
                  <p className="mt-3 flex items-center gap-2 text-sm">
                    <Swatch color={MACRO_COLOR[r.macro]} />
                    Categoría principal: <span className="font-medium">{CATEGORY_LABEL[r.category]}</span>
                  </p>
                )}
                <div className="mt-5 space-y-4">
                  <Meter label="Toxicidad combinada" value={r.toxicity} threshold={r.thresholds.toxicity} />
                  <Meter label="Odio por identidad" value={r.identity} threshold={r.thresholds.identity} />
                  <Meter label="Riesgo de crisis" value={r.crisis} threshold={r.thresholds.crisis} />
                </div>

                {cats.length > 0 && (
                  <>
                    <h3 className="mt-6 font-serif text-[15px] font-semibold">Puntaje por categoría</h3>
                    <ul className="mt-2 space-y-1.5 text-sm">
                      {cats.map(([c, s]) => (
                        <li key={c} className="flex items-center gap-2">
                          <Swatch color={MACRO_COLOR[CATEGORY_MACRO[c]]} />
                          <span className="w-44 truncate">{CATEGORY_LABEL[c]}</span>
                          <div className="h-1.5 flex-1 rounded-full bg-sunken">
                            <div className="h-full rounded-full" style={{ width: `${s * 100}%`, background: MACRO_COLOR[CATEGORY_MACRO[c]] }} />
                          </div>
                          <span className="w-10 text-right tabular-nums text-ink-2">{score(s)}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                <h3 className="mt-6 font-serif text-[15px] font-semibold">Veredicto por modelo</h3>
                <ul className="mt-2 divide-y divide-line rounded-md border border-line text-sm">
                  {r.providers.map((p) => (
                    <li key={p.name} className="px-3 py-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">{PROVIDER_LABEL[p.name] ?? p.name}</span>
                        {p.error ? (
                          <span className="text-xs text-danger">sin respuesta</span>
                        ) : (
                          <span className="tabular-nums text-ink-2">
                            tox. {score(p.toxicity ?? 0)}
                            {p.top_category && p.top_category !== "self_harm" ? `, ${CATEGORY_LABEL[p.top_category]}` : ""}
                            {p.latency_ms !== null ? `, ${Math.round(p.latency_ms)} ms` : ""}
                          </span>
                        )}
                      </div>
                      {(p.rationale || p.error) && <p className="mt-1 text-[12.5px] text-muted">{p.error ?? p.rationale}</p>}
                    </li>
                  ))}
                  {r.safety_net && (
                    <li className="px-3 py-2.5">
                      <div className="font-medium">Red de seguridad léxica</div>
                      <p className="mt-1 text-[12.5px] text-muted">{r.safety_net}</p>
                    </li>
                  )}
                </ul>
                {r.providers.every((p) => p.name === "heuristic" || p.error) && (
                  <p className="mt-4 text-[13px] text-ink-2">
                    Ningún modelo de lenguaje respondió; solo se usaron reglas. Revisa que GROQ_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY o EDENAI_API_KEY estén configuradas y vuelve a desplegar.
                  </p>
                )}
              </Figure>
            </motion.div>
          ) : (
            <Figure title="Decisión">
              <p className="text-sm text-ink-2">El resultado aparecerá aquí: qué haría el bot, qué categoría detectó y qué opinó cada modelo.</p>
            </Figure>
          )}
        </AnimatePresence>
      </div>
    </>
  );
}
