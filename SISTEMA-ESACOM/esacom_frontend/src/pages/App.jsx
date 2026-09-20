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

function DashboardProtegido() {
  return (
    <RutaProtegida>
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

          <Route path="/dashboard" element={<DashboardProtegido />} />
          <Route path="/supervisor" element={<DashboardProtegido />} />
          <Route path="/mi-portal" element={<DashboardProtegido />} />
          <Route path="/soporte" element={<DashboardProtegido />} />
          <Route path="/operaciones" element={<DashboardProtegido />} />
          <Route path="/contabilidad" element={<DashboardProtegido />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}