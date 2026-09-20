import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { rutaPorCargo } from "../pages/Login";

/**
 * Envuelve una ruta que requiere sesión iniciada. Si además se pasa
 * `cargosPermitidos`, un usuario logueado pero con otro rol es
 * redirigido a SU portal (no a un error) -- ej. un Ejecutivo que
 * intenta entrar a /dashboard termina en /mi-portal, no en una
 * pantalla de "no autorizado".
 */
export default function RutaProtegida({ children, cargosPermitidos, permisoRequerido }) {
  const { user, cargando } = useAuth();
  const location = useLocation();

  if (cargando) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-gray-400">
        Cargando…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (cargosPermitidos && !cargosPermitidos.includes(user.cargo)) {
    return <Navigate to="/sin-acceso" replace />;
  }
  if (permisoRequerido && !user?.permisos?.[permisoRequerido]) {
    return <Navigate to="/sin-acceso" replace />;
  }

  return children;
}
