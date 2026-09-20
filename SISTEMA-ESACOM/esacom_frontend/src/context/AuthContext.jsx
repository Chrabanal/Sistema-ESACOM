import { createContext, useContext, useEffect, useState } from "react";
import * as authApi from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    // Si ya hay un token guardado (recarga de página), intenta
    // recuperar la sesión antes de mostrar nada.
    const tieneToken = !!localStorage.getItem("esacom_access");
    if (!tieneToken) {
      setCargando(false);
      return;
    }
    authApi
      .fetchMe()
      .then(setUser)
      .catch(() => authApi.logout())
      .finally(() => setCargando(false));
  }, []);

  async function login(rut, password) {
    await authApi.login(rut, password);
    const me = await authApi.fetchMe();
    setUser(me);
    return me;
  }

  async function logout() {
    await authApi.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, cargando, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
