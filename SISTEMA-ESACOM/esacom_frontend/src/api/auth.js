import client, { setTokens, clearTokens, getRefreshToken } from "./client";

/**
 * POST /api/auth/login/ -- el backend espera {rut, password} y
 * devuelve {access, refresh}. El RUT se manda tal cual lo escribe
 * el usuario; la normalización (sin puntos, con guion) la hace el
 * backend (ver usuarios/models.py: EjecutivoManager.normalize_rut).
 */
export async function login(rut, password) {
  const { data } = await client.post("/auth/login/", { rut, password });
  setTokens(data);
  return data;
}

export async function logout() {
  const refresh = getRefreshToken();
  try {
    if (refresh) await client.post('/auth/logout/', { refresh });
  } catch {
    // El cierre local no debe quedar bloqueado por una falla de red/API.
  } finally {
    clearTokens();
  }
}

/**
 * GET /api/ejecutivos/me/ -- perfil del usuario logueado. El campo
 * `cargo` (GERENCIA / SUPERVISOR / EJECUTIVO) define a qué portal
 * redirigir después del login.
 */
export async function fetchMe() {
  const { data } = await client.get("/ejecutivos/me/");
  return data;
}
