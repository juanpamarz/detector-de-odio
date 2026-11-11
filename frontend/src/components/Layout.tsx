import { clsx } from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { FlaskConical, LayoutDashboard, LogOut, Menu, Monitor, Moon, ShieldAlert, Sun, Users, UsersRound, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/categories";
import { PERIODS, usePeriod, type PeriodDays } from "@/lib/period";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { Segmented } from "./ui";

const NAV = [
  { to: "/", label: "Panorama", icon: LayoutDashboard, end: true },
  { to: "/grupos", label: "Grupos", icon: UsersRound },
  { to: "/incidentes", label: "Incidentes", icon: ShieldAlert },
];

function Mark() {
  return (
    <svg viewBox="0 0 64 40" className="h-6 w-9" aria-hidden>
      <path d="M3 20 Q32 -4 61 20 Q32 44 3 20Z" fill="none" stroke="currentColor" strokeWidth="3.5" />
      <circle cx="32" cy="20" r="8.5" fill="currentColor" />
    </svg>
  );
}

function ThemeSwitch() {
  const { mode, setMode } = useTheme();
  const options: { value: ThemeMode; icon: typeof Sun; label: string }[] = [
    { value: "light", icon: Sun, label: "Claro" },
    { value: "system", icon: Monitor, label: "Sistema" },
    { value: "dark", icon: Moon, label: "Oscuro" },
  ];
  return (
    <div role="radiogroup" aria-label="Tema" className="flex rounded-md border border-line bg-sunken p-0.5">
      {options.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          role="radio"
          aria-checked={mode === value}
          title={label}
          onClick={() => setMode(value)}
          className={clsx("flex h-7 flex-1 items-center justify-center rounded transition-colors", mode === value ? "bg-panel text-ink ring-1 ring-line" : "text-muted hover:text-ink")}
        >
          <Icon size={14} />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout, can } = useAuth();
  const items = [
    ...NAV,
    ...(can("admin", "moderator") ? [{ to: "/probar", label: "Probar mensajes", icon: FlaskConical }] : []),
    ...(can("admin") ? [{ to: "/usuarios", label: "Cuentas del panel", icon: Users }] : []),
  ];
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 pb-6 pt-6 text-brand">
        <Mark />
        <div>
          <div className="font-serif text-[19px] font-semibold leading-none text-ink">Centinela</div>
          <div className="mt-1 text-2xs text-muted">Convivencia en grupos de Telegram</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-3">
        {items.map(({ to, label, icon: Icon, ...rest }) => (
          <NavLink
            key={to}
            to={to}
            end={"end" in rest}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx("relative flex h-9 items-center gap-2.5 rounded-md px-3 text-sm transition-colors", isActive ? "text-ink" : "text-ink-2 hover:bg-sunken hover:text-ink")
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-md bg-sunken ring-1 ring-line" transition={{ type: "spring", stiffness: 400, damping: 34 }} />}
                <Icon size={16} className="relative" />
                <span className="relative">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-3 border-t border-line p-4">
        <ThemeSwitch />
        {user && (
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{user.full_name}</div>
              <div className="text-2xs text-muted">{ROLE_LABEL[user.role]}</div>
            </div>
            <button onClick={logout} className="btn-ghost h-8 px-2" title="Cerrar sesión">
              <LogOut size={15} />
              <span className="sr-only">Cerrar sesión</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function Layout() {
  const [open, setOpen] = useState(false);
  const { days, setDays } = usePeriod();
  const location = useLocation();
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="sticky top-0 hidden h-screen border-r border-line bg-panel lg:block">
        <Sidebar />
      </aside>

      <AnimatePresence>
        {open && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-black/40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-[264px] border-r border-line bg-panel lg:hidden"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 380, damping: 38 }}
            >
              <Sidebar onNavigate={() => setOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="min-w-0">
        <div className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-line bg-canvas/85 px-4 backdrop-blur md:px-8">
          <button className="btn-ghost h-8 px-2 lg:hidden" onClick={() => setOpen((v) => !v)} aria-label="Abrir menú">
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
          <span className="hidden text-[13px] text-ink-2 lg:block">Periodo de análisis</span>
          <Segmented<PeriodDays> label="Periodo" value={days} onChange={setDays} options={PERIODS.map((p) => ({ value: p.days, label: p.label }))} />
        </div>
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.25 }}
          className="mx-auto max-w-[1320px] px-4 py-8 md:px-8"
        >
          <Outlet />
        </motion.main>
      </div>
    </div>
  );
}
