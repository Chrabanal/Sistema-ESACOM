import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./context/AuthContext";
import RutaProtegida from "./components/RutaProtegida";

import Login, { rutaPorCargo } from "./pages/Login";
import DashboardBase from "./pages/DashboardBase";
import SinAcceso from "./pages/SinAcceso";

function Inicio() {
  const { user, cargando } = useAuth();

  if (cargando) {
    return null;
  }

  return (
    <Navigate
      to={user ? rutaPorCargo(user.cargo) : "/login"}
      replace
    />
  );
}

function DashboardProtegido({ cargosPermitidos, permisoRequerido }) {
  return (
    <RutaProtegida
      cargosPermitidos={cargosPermitidos}
      permisoRequerido={permisoRequerido}
    >
      <DashboardBase />
    </RutaProtegida>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Inicio />} />

          <Route path="/login" element={<Login />} />
          <Route path="/sin-acceso" element={<SinAcceso />} />

          <Route
            path="/dashboard"
            element={
              <DashboardProtegido
                cargosPermitidos={["GERENCIA"]}
                permisoRequerido="dashboard_gerencia"
              />
            }
          />
          <Route
            path="/supervisor"
            element={
              <DashboardProtegido
                cargosPermitidos={["SUPERVISOR"]}
                permisoRequerido="mi_equipo"
              />
            }
          />
          <Route
            path="/mi-portal"
            element={
              <DashboardProtegido
                cargosPermitidos={["EJECUTIVO"]}
                permisoRequerido="mi_portal"
              />
            }
          />
          <Route
            path="/soporte"
            element={
              <DashboardProtegido
                cargosPermitidos={["SOPORTE"]}
                permisoRequerido="usuarios"
              />
            }
          />
          <Route
            path="/operaciones"
            element={<DashboardProtegido cargosPermitidos={["OPERACIONES"]} />}
          />
          <Route
            path="/contabilidad"
            element={<DashboardProtegido cargosPermitidos={["CONTABILIDAD"]} />}
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}