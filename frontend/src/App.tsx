import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Empty } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import Login from "@/pages/Login";

const Overview = lazy(() => import("@/pages/Overview"));
const Groups = lazy(() => import("@/pages/Groups"));
const GroupDetail = lazy(() => import("@/pages/GroupDetail"));
const Incidents = lazy(() => import("@/pages/Incidents"));
const Users = lazy(() => import("@/pages/Users"));
const Lab = lazy(() => import("@/pages/Lab"));

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { can } = useAuth();
  return can("admin") ? <>{children}</> : <Empty title="Acceso restringido" body="Solo la administración puede gestionar cuentas del panel." />;
}

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Overview />} />
          <Route path="grupos" element={<Groups />} />
          <Route path="grupos/:id" element={<GroupDetail />} />
          <Route path="incidentes" element={<Incidents />} />
          <Route path="probar" element={<Lab />} />
          <Route
            path="usuarios"
            element={
              <RequireAdmin>
                <Users />
              </RequireAdmin>
            }
          />
          <Route path="*" element={<Empty title="Página no encontrada" body="Vuelve al panorama desde el menú lateral." />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
