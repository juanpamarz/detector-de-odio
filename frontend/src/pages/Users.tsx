import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Plus } from "lucide-react";
import { Badge, ErrorNote, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/categories";
import { relative } from "@/lib/format";
import { useUsers } from "@/lib/queries";
import type { Role, User } from "@/lib/types";

const ROLE_HELP: Record<Role, string> = {
  admin: "Todo, incluida la gestión de cuentas.",
  moderator: "Consultar, exportar y ajustar umbrales de grupos.",
  analyst: "Consultar y exportar.",
};

function NewUserForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "analyst" as Role });
  const create = useMutation({
    mutationFn: () => api<User>("/users", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <motion.form initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} onSubmit={submit} className="overflow-hidden border-b border-line">
      <div className="grid gap-3 p-4 md:grid-cols-4">
        <input className="input" placeholder="Nombre completo" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <input className="input" type="email" placeholder="Correo" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input className="input" type="password" placeholder="Contraseña (mín. 10 caracteres)" minLength={10} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <div className="flex gap-2">
          <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
          <button className="btn-primary shrink-0" disabled={create.isPending}>
            {create.isPending && <Loader2 size={15} className="animate-spin" />}
            Crear cuenta
          </button>
        </div>
      </div>
      <p className="px-4 pb-3 text-[13px] text-ink-2">
        {create.isError ? <span className="text-danger">{(create.error as Error).message}</span> : ROLE_HELP[form.role]}
      </p>
    </motion.form>
  );
}

export default function Users() {
  const q = useUsers();
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Pick<User, "role" | "is_active">> }) => api<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <>
      <PageHeader
        title="Cuentas del panel"
        description="Quién puede ver y operar este panel. Las contraseñas se guardan con bcrypt y las sesiones expiran automáticamente."
        actions={
          <button className="btn-primary" onClick={() => setAdding((v) => !v)}>
            <Plus size={15} /> Nueva cuenta
          </button>
        }
      />
      <div className="panel overflow-hidden">
        <AnimatePresence>{adding && <NewUserForm onDone={() => setAdding(false)} />}</AnimatePresence>
        {q.isError ? (
          <ErrorNote error={q.error} />
        ) : !q.data ? (
          <div className="space-y-2 p-4">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[12.5px] text-ink-2">
                  <th className="px-4 py-2.5 font-medium">Persona</th>
                  <th className="px-4 py-2.5 font-medium">Rol</th>
                  <th className="px-4 py-2.5 font-medium">Último acceso</th>
                  <th className="px-4 py-2.5 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((u) => {
                  const self = u.id === me?.id;
                  return (
                    <tr key={u.id} className="border-b border-line last:border-0">
                      <td className="px-4 py-3">
                        <div className="font-medium">
                          {u.full_name} {self && <Badge>tú</Badge>}
                        </div>
                        <div className="text-[13px] text-ink-2">{u.email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <select className="input h-8 w-auto" value={u.role} disabled={self} onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value as Role } })} aria-label={`Rol de ${u.full_name}`}>
                          {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
                            <option key={r} value={r}>
                              {ROLE_LABEL[r]}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-ink-2">{u.last_login_at ? relative(u.last_login_at) : "Nunca"}</td>
                      <td className="px-4 py-3">
                        <button className="btn-ghost h-8" disabled={self} onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                          {u.is_active ? "Desactivar" : "Activar"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
