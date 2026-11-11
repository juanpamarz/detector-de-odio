import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, Plus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { relative } from "@/lib/format";
import { useBotStatus } from "@/lib/queries";
import { Badge, Skeleton } from "./ui";

const PROVIDER_LABEL: Record<string, string> = {
  groq: "Groq",
  cerebras: "Cerebras",
  openrouter: "OpenRouter",
  edenai: "Eden AI",
  heuristic: "Reglas",
};

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <li className="flex gap-2.5">
      {ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-good" aria-label="Correcto" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0 text-danger" aria-label="Requiere atención" />}
      <span className="text-[13.5px] leading-relaxed">{children}</span>
    </li>
  );
}

/** Estado del bot, conexión y registro de grupos: explica por qué un grupo no aparece. */
export function BotPanel() {
  const status = useBotStatus();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [chat, setChat] = useState("");
  const invalidate = () => qc.invalidateQueries({ predicate: (q) => ["groups", "group", "bot-status"].includes(String(q.queryKey[0])) });

  const register = useMutation({
    mutationFn: () => api<{ title: string }>("/bot/groups", { method: "POST", body: JSON.stringify({ chat }) }),
    onSuccess: () => {
      setChat("");
      void invalidate();
    },
  });
  const refreshAll = useMutation({
    mutationFn: () => api<{ checked: number; unreachable: number }>("/bot/groups/refresh", { method: "POST" }),
    onSuccess: () => void invalidate(),
  });
  const webhook = useMutation({
    mutationFn: () => api<{ webhook_url: string }>("/bot/webhook", { method: "POST" }),
    onSuccess: () => void invalidate(),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (chat.trim()) register.mutate();
  };
  const s = status.data;
  const webhookOk = s ? (s.queue_backend === "qstash" ? s.webhook_url === s.expected_webhook_url : true) : false;

  return (
    <section className="panel mb-6 grid gap-6 p-5 lg:grid-cols-[1.2fr_1fr]">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-serif text-[17px] font-semibold">Estado del bot</h2>
          {s && <Badge tone="brand">@{s.username}</Badge>}
          {s && <Badge>{s.queue_backend === "qstash" ? "Serverless (QStash)" : "Workers Celery"}</Badge>}
        </div>
        {status.isError ? (
          <p className="mt-3 text-sm text-danger">{(status.error as Error).message}</p>
        ) : !s ? (
          <Skeleton className="mt-3 h-24" />
        ) : (
          <ul className="mt-3 space-y-2">
            <Check ok={!s.privacy_mode}>
              {s.privacy_mode ? (
                <>
                  <b>Modo privacidad activado</b>: el bot solo recibe comandos, no los mensajes normales, por eso no modera ni registra los grupos. En @BotFather envía <code>/setprivacy</code>, elige el bot, selecciona <b>Disable</b> y vuelve a agregarlo a cada grupo.
                </>
              ) : (
                "El bot puede leer todos los mensajes de los grupos."
              )}
            </Check>
            <Check ok={webhookOk}>
              {s.mode === "webhook" ? (
                <>
                  Recibe mensajes por webhook{s.pending_updates ? `, ${s.pending_updates} pendientes` : ""}.
                  {!webhookOk && " La dirección registrada en Telegram no coincide con esta instalación."}
                </>
              ) : s.queue_backend === "qstash" ? (
                "No hay webhook conectado: Telegram no está enviando mensajes a esta instalación."
              ) : (
                "Recibe mensajes por long-polling (servicio bot de docker compose)."
              )}
            </Check>
            {s.last_error && (
              <Check ok={false}>
                Último error de entrega {s.last_error_at ? relative(s.last_error_at) : ""}: {s.last_error}
              </Check>
            )}
          </ul>
        )}
        {s && can("admin") && s.queue_backend === "qstash" && (
          <button className="btn-ghost mt-4" onClick={() => webhook.mutate()} disabled={webhook.isPending}>
            {webhook.isPending && <Loader2 size={15} className="animate-spin" />}
            {s.webhook_url ? "Volver a conectar webhook" : "Conectar webhook"}
          </button>
        )}
        {webhook.isError && <p className="mt-2 text-sm text-danger">{(webhook.error as Error).message}</p>}

        {s && (
          <div className="mt-5">
            <div className="mb-2 text-[13px] text-ink-2">Cadena de modelos (en orden; si uno falla se usa el siguiente)</div>
            <div className="flex flex-wrap gap-1.5">
              {s.providers.map((p, i) => (
                <span key={p.name} className="inline-flex items-center gap-1.5 rounded-md border border-line px-2 py-1 text-[12.5px]">
                  <span className="tabular-nums text-muted">{i + 1}</span>
                  {PROVIDER_LABEL[p.name] ?? p.name}
                  {!p.available && <span className="text-danger">en espera {p.cooldown_seconds} s</span>}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-line pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
        <h2 className="font-serif text-[17px] font-semibold">¿Falta un grupo?</h2>
        <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
          Telegram no deja que un bot liste sus grupos; cada grupo aparece cuando llega algo desde él. La forma más rápida: escribe <code>/registrar</code> dentro del grupo (funciona aunque el modo privacidad esté activado) y el bot responderá con sus permisos.
        </p>
        {can("admin", "moderator") && (
          <>
            <form onSubmit={submit} className="mt-4 flex gap-2">
              <input className="input" placeholder="ID del grupo (-100…) o @usuario" value={chat} onChange={(e) => setChat(e.target.value)} aria-label="ID o usuario del grupo" />
              <button className="btn-primary shrink-0" disabled={register.isPending || !chat.trim()}>
                {register.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                Agregar
              </button>
            </form>
            {register.isError && <p className="mt-2 text-sm text-danger">{(register.error as Error).message}</p>}
            {register.isSuccess && <p className="mt-2 text-sm text-good">Grupo «{register.data.title}» registrado.</p>}
            <button className="btn-ghost mt-3" onClick={() => refreshAll.mutate()} disabled={refreshAll.isPending}>
              {refreshAll.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
              Verificar permisos de todos los grupos
            </button>
            {refreshAll.isSuccess && (
              <p className="mt-2 text-[13px] text-ink-2">
                {refreshAll.data.checked} verificados{refreshAll.data.unreachable ? `, ${refreshAll.data.unreachable} sin acceso (el bot ya no está en ellos)` : ""}.
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

export function PermissionBadge({ status, canDelete }: { status: string | null; canDelete: boolean | null }) {
  if (!status) return <Badge>Sin verificar</Badge>;
  if (status === "left" || status === "kicked") return <Badge tone="danger">Fuera del grupo</Badge>;
  if (status !== "administrator" && status !== "creator") return <Badge tone="danger">No es admin</Badge>;
  if (!canDelete) return <Badge tone="danger">Sin permiso de borrar</Badge>;
  return <Badge tone="good">Listo</Badge>;
}
