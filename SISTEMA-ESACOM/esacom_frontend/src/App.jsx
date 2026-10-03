import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import RutaProtegida from "./components/RutaProtegida";
import { rutaPorCargo } from "./pages/Login";
import Login from "./pages/Login";
import DashboardGerencia from "./pages/DashboardGerencia";
import CierresKPI from "./pages/CierresKPI";
import SeguimientoEjecutivos from "./pages/SeguimientoEjecutivos";
import SeguimientoBoletas from "./pages/SeguimientoBoletas";
import Apelaciones from "./pages/Apelaciones";
import BaseDatos from "./pages/BaseDatos";
import Historico from "./pages/Historico";
import CargarDatos from "./pages/CargarDatos";
import AuditoriaKPI from "./pages/AuditoriaKPI";
import Analisis from "./pages/Analisis";
import PortalSupervisor from "./pages/PortalSupervisor";
import PortalEjecutivo from "./pages/PortalEjecutivo";
import DashboardSoporte from "./pages/DashboardSoporte";
import Cobranza from "./pages/Cobranza";
import Permisos from "./pages/Permisos";
import PortalOperaciones from "./pages/PortalOperaciones";
import PortalContabilidad from "./pages/PortalContabilidad";
import EstadoSistema from "./pages/EstadoSistema";
import SinAcceso from "./pages/SinAcceso";

function RaizSegunSesion() {
  const { user, cargando } = useAuth();
  if (cargando) return null;
  return <Navigate to={user ? rutaPorCargo(user.cargo) : "/login"} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<RaizSegunSesion />} />
          <Route path="/login" element={<Login />} />
          <Route path="/sin-acceso" element={<SinAcceso />} />

          <Route
            path="/dashboard"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA"]} permisoRequerido="dashboard_gerencia">
                <DashboardGerencia />
              </RutaProtegida>
            }
          />
          <Route
            path="/cierres-kpi"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA"]} permisoRequerido="dashboard_gerencia">
                <CierresKPI />
              </RutaProtegida>
            }
          />
          <Route
            path="/ejecutivos"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA"]} permisoRequerido="dashboard_gerencia">
                <SeguimientoEjecutivos />
              </RutaProtegida>
            }
          />
          <Route
            path="/accionables"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "OPERACIONES", "SUPERVISOR", "EJECUTIVO"]} permisoRequerido="accionables">
                <SeguimientoBoletas />
              </RutaProtegida>
            }
          />
          <Route
            path="/cobranza"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "CONTABILIDAD", "OPERACIONES"]} permisoRequerido="cobranza">
                <Cobranza />
              </RutaProtegida>
            }
          />
          <Route
            path="/apelaciones"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "OPERACIONES", "CONTABILIDAD"]} permisoRequerido="apelaciones">
                <Apelaciones />
              </RutaProtegida>
            }
          />
          <Route
            path="/cargar-datos"
            element={
              <RutaProtegida cargosPermitidos={["SOPORTE"]} permisoRequerido="cargar_datos">
                <CargarDatos />
              </RutaProtegida>
            }
          />
          <Route
            path="/analisis"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "OPERACIONES"]} permisoRequerido="analisis">
                <Analisis />
              </RutaProtegida>
            }
          />
          <Route
            path="/auditoria-kpi"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "OPERACIONES", "CONTABILIDAD"]} permisoRequerido="auditoria_kpi">
                <AuditoriaKPI />
              </RutaProtegida>
            }
          />
          <Route
            path="/base-datos"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "OPERACIONES"]} permisoRequerido="base_datos">
                <BaseDatos />
              </RutaProtegida>
            }
          />
          <Route
            path="/historico"
            element={
              <RutaProtegida cargosPermitidos={["GERENCIA", "OPERACIONES", "CONTABILIDAD"]} permisoRequerido="historico">
                <Historico />
              </RutaProtegida>
            }
          />
          <Route
            path="/operaciones"
            element={<RutaProtegida cargosPermitidos={["OPERACIONES"]}><PortalOperaciones /></RutaProtegida>}
          />
          <Route
            path="/contabilidad"
            element={<RutaProtegida cargosPermitidos={["CONTABILIDAD"]}><PortalContabilidad /></RutaProtegida>}
          />

          <Route
            path="/supervisor"
            element={
              <RutaProtegida cargosPermitidos={["SUPERVISOR", "GERENCIA"]} permisoRequerido="mi_equipo">
                <PortalSupervisor />
              </RutaProtegida>
            }
          />
          <Route
            path="/mi-portal"
            element={
              <RutaProtegida cargosPermitidos={["EJECUTIVO"]} permisoRequerido="mi_portal">
                <PortalEjecutivo />
              </RutaProtegida>
            }
          />

          <Route
            path="/soporte"
            element={
              <RutaProtegida cargosPermitidos={["SOPORTE"]} permisoRequerido="usuarios">
                <DashboardSoporte />
              </RutaProtegida>
            }
          />

          <Route path="/permisos" element={<RutaProtegida cargosPermitidos={["SOPORTE","GERENCIA"]} permisoRequerido="permisos"><Permisos /></RutaProtegida>} />
          <Route path="/estado-sistema" element={<RutaProtegida cargosPermitidos={["SOPORTE","GERENCIA"]} permisoRequerido="estado_sistema"><EstadoSistema /></RutaProtegida>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
