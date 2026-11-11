import { useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { WatchfulEye, type EyeMode, type EyeStatus } from "@/components/WatchfulEye";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [focus, setFocus] = useState<"email" | "password" | null>(null);
  const [status, setStatus] = useState<EyeStatus>("none");
  const [error, setError] = useState<string | null>(null);

  if (user && status !== "success") return <Navigate to="/" replace />;

  const mode: EyeMode = focus === "email" ? "email" : focus === "password" ? (show ? "peek" : "password") : "idle";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus("loading");
    try {
      await login(email, password);
      setStatus("success");
      const to = (location.state as { from?: string } | null)?.from ?? "/";
      setTimeout(() => navigate(to, { replace: true }), 450);
    } catch (err) {
      setStatus("error");
      setError(
        err instanceof ApiError && err.status === 401
          ? "Correo o contraseña incorrectos."
          : err instanceof ApiError && err.status < 500
            ? err.message
            : "No hay conexión con el servidor. Intenta de nuevo en unos segundos.",
      );
      setTimeout(() => setStatus("none"), 600);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden border-r border-line bg-panel lg:flex lg:flex-col lg:justify-between lg:p-14">
        <svg className="pointer-events-none absolute -right-40 top-1/2 h-[720px] w-[720px] -translate-y-1/2 text-line" viewBox="0 0 200 200" aria-hidden>
          {[96, 80, 64, 48, 32].map((r) => (
            <circle key={r} cx="100" cy="100" r={r} fill="none" stroke="currentColor" strokeWidth="0.35" />
          ))}
          {Array.from({ length: 72 }, (_, i) => {
            const a = (i / 72) * Math.PI * 2;
            const r2 = i % 6 === 0 ? 90 : 93;
            return <line key={i} x1={100 + Math.cos(a) * 96} y1={100 + Math.sin(a) * 96} x2={100 + Math.cos(a) * r2} y2={100 + Math.sin(a) * r2} stroke="currentColor" strokeWidth="0.35" />;
          })}
        </svg>
        <div className="relative flex items-center gap-4 text-brand">
          <svg viewBox="0 0 64 40" className="h-11 w-[70px]" aria-hidden>
            <path d="M3 20 Q32 -4 61 20 Q32 44 3 20Z" fill="none" stroke="currentColor" strokeWidth="3.5" />
            <circle cx="32" cy="20" r="8.5" fill="currentColor" />
          </svg>
          <span className="font-serif text-[52px] font-semibold leading-none tracking-tight text-ink">Centinela</span>
        </div>
        <div className="relative max-w-[30rem]">
          <h1 className="font-serif text-[44px] font-semibold leading-[1.08]">Observar la conversación para cuidar a quienes participan en ella.</h1>
          <p className="mt-6 max-w-[34rem] text-[16px] leading-relaxed text-ink-2">
            Cada mensaje de los grupos se evalúa con varios modelos de lenguaje. Lo que hiere se retira en segundos, quien atraviesa una crisis recibe apoyo en privado y cada decisión queda registrada para su revisión.
          </p>
        </div>
        <p className="relative text-[13px] text-muted">Proyecto de Ingeniería en Ciencia y Analítica de Datos, Universidad Autónoma de Querétaro.</p>
      </section>

      <section className="flex items-center justify-center px-5 py-12">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }} className="w-full max-w-[380px]">
          <div className="mb-2 text-center font-serif text-[40px] font-semibold leading-none tracking-tight lg:hidden">Centinela</div>
          <div className="mb-6 flex justify-center">
            <WatchfulEye mode={mode} status={status} caret={email.length} />
          </div>
          <h2 className="text-center text-[26px] font-semibold">Iniciar sesión</h2>
          <p className="mt-1.5 text-center text-sm text-ink-2">Usa la cuenta que te asignó la administración del panel.</p>

          <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-[13px] font-medium">
                Correo
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                required
                className="input h-10"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => setFocus("email")}
                onBlur={() => setFocus(null)}
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-[13px] font-medium">
                Contraseña
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  className="input h-10 pr-10"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setFocus("password")}
                  onBlur={() => setFocus(null)}
                />
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setShow((v) => !v)}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted hover:text-ink"
                  aria-label={show ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div aria-live="polite" className="min-h-[1.25rem] text-[13px] text-danger">
              {error}
            </div>

            <button type="submit" className="btn-primary h-10 w-full" disabled={status === "loading" || !email || !password}>
              {status === "loading" ? <Loader2 size={16} className="animate-spin" /> : null}
              {status === "loading" ? "Verificando" : "Entrar"}
            </button>
          </form>
        </motion.div>
      </section>
    </div>
  );
}
