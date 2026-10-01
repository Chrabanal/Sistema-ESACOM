import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./context/AuthContext";
import RutaProtegida from "./components/RutaProtegida";

import Login, { rutaPorCargo } from "./pages/Login";
import DashboardBase from "./pages/DashboardBase";
import SinAcceso from "./pages/SinAcceso";

import PortalEjecutivo from "./pages/PortalEjecutivo";
import PortalSupervisor from "./pages/PortalSupervisor";
import DashboardGerencia from "./pages/DashboardGerencia";
import DashboardSoporte from "./pages/DashboardSoporte";

import Historico from "./pages/Historico";
import AuditoriaKPI from "./pages/AuditoriaKPI";
import SeguimientoEjecutivos from "./pages/SeguimientoEjecutivos";
import SeguimientoBoletas from "./pages/SeguimientoBoletas";
import Analisis from "./pages/Analisis";

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

function DashboardProtegido({
  cargosPermitidos,
  permisoRequerido,
  children,
}) {
  return (
    <RutaProtegida
      cargosPermitidos={cargosPermitidos}
      permisoRequerido={permisoRequerido}
    >
      {children || <DashboardBase />}
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
              >
                <DashboardGerencia />
              </DashboardProtegido>
            }
          />

          <Route
            path="/supervisor"
            element={
              <DashboardProtegido
                cargosPermitidos={["SUPERVISOR"]}
                permisoRequerido="mi_equipo"
              >
                <PortalSupervisor />
              </DashboardProtegido>
            }
          />

          <Route
            path="/mi-portal"
            element={
              <DashboardProtegido
                cargosPermitidos={["EJECUTIVO"]}
                permisoRequerido="mi_portal"
              >
                <PortalEjecutivo />
              </DashboardProtegido>
            }
          />

          <Route
            path="/historico"
            element={
              <DashboardProtegido
                cargosPermitidos={["GERENCIA", "SUPERVISOR"]}
              >
                <Historico />
              </DashboardProtegido>
            }
          />

          <Route
            path="/ejecutivos"
            element={
              <DashboardProtegido
                cargosPermitidos={["GERENCIA", "SUPERVISOR"]}
              >
                <SeguimientoEjecutivos />
              </DashboardProtegido>
            }
          />

          <Route
            path="/accionables"
            element={
              <DashboardProtegido
                cargosPermitidos={["GERENCIA", "SUPERVISOR", "EJECUTIVO"]}
                permisoRequerido="accionables"
              >
                <SeguimientoBoletas />
              </DashboardProtegido>
            }
          />

          <Route
            path="/analisis"
            element={
              <DashboardProtegido
                cargosPermitidos={["GERENCIA"]}
                permisoRequerido="analisis"
              >
                <Analisis />
              </DashboardProtegido>
            }
          />

          <Route
            path="/auditoria-kpi"
            element={
              <DashboardProtegido
                cargosPermitidos={["GERENCIA"]}
                permisoRequerido="auditoria_kpi"
              >
                <AuditoriaKPI />
              </DashboardProtegido>
            }
          />

          <Route
            path="/soporte"
            element={
              <DashboardProtegido
                cargosPermitidos={["SOPORTE"]}
                permisoRequerido="usuarios"
              >
                <DashboardSoporte />
              </DashboardProtegido>
            }
          />

          <Route
            path="/operaciones"
            element={
              <DashboardProtegido cargosPermitidos={["OPERACIONES"]} />
            }
          />

          <Route
            path="/contabilidad"
            element={
              <DashboardProtegido cargosPermitidos={["CONTABILIDAD"]} />
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
