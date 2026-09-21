import type { ReactNode } from "react";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import Login from "@/pages/auth/Login";
import GuardDashboard from "@/pages/guard/GuardDashboard";
import ParkingMapPage from "@/pages/user/ParkingMapPage";
import type { RolUsuario } from "@/types/api";
import { rutaInicioPara } from "@/utils/rutas";

function RutaProtegida({
  children,
  rolesPermitidos,
}: {
  children: ReactNode;
  rolesPermitidos?: RolUsuario[];
}) {
  const { usuario, cargando } = useAuth();

  if (cargando) {
    return <p className="p-6 text-center text-gray-400">Cargando...</p>;
  }
  if (!usuario) {
    return <Navigate to="/login" replace />;
  }
  if (rolesPermitidos && !rolesPermitidos.includes(usuario.rol)) {
    return <Navigate to={rutaInicioPara(usuario.rol)} replace />;
  }
  return <>{children}</>;
}

function InicioSegunRol() {
  const { usuario, cargando } = useAuth();
  if (cargando) {
    return <p className="p-6 text-center text-gray-400">Cargando...</p>;
  }
  return <Navigate to={usuario ? rutaInicioPara(usuario.rol) : "/login"} replace />;
}

function Rutas() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/vigilante"
        element={
          <RutaProtegida rolesPermitidos={["vigilante", "admin"]}>
            <GuardDashboard />
          </RutaProtegida>
        }
      />
      <Route
        path="/mapa"
        element={
          <RutaProtegida>
            <ParkingMapPage />
          </RutaProtegida>
        }
      />
      <Route
        path="/admin"
        element={
          <RutaProtegida rolesPermitidos={["admin"]}>
            <AdminDashboard />
          </RutaProtegida>
        }
      />
      <Route path="*" element={<InicioSegunRol />} />
    </Routes>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Rutas />
      </AuthProvider>
    </Router>
  );
}
