import axios from "axios";

// En desarrollo apunta al backend local (Día 1-5). En producción se
// define VITE_API_URL en el .env del build.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// El panel de Admin vive en Django, no en esta SPA -- mismo host, sin el /api.
export const ADMIN_URL = API_URL.replace(/\/api\/?$/, "") + "/admin/";

const client = axios.create({ baseURL: API_URL });

export function getTokens() {
  return {
    access: localStorage.getItem("esacom_access"),
    refresh: localStorage.getItem("esacom_refresh"),
  };
}

export function getRefreshToken() {
  return localStorage.getItem("esacom_refresh");
}

export function setTokens({ access, refresh }) {
  if (access) localStorage.setItem("esacom_access", access);
  if (refresh) localStorage.setItem("esacom_refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("esacom_access");
  localStorage.removeItem("esacom_refresh");
}

client.interceptors.request.use((config) => {
  const { access } = getTokens();
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

// Si el access token expiró (401), intenta refrescarlo una vez y
// reintenta la petición original antes de rendirse.
let refrescando = null;

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }
    original._retry = true;

    const { refresh } = getTokens();
    if (!refresh) {
      clearTokens();
      return Promise.reject(error);
    }

    try {
      if (!refrescando) {
        refrescando = axios
          .post(`${API_URL}/auth/refresh/`, { refresh })
          .then((res) => {
            // Con ROTATE_REFRESH_TOKENS=True SimpleJWT puede devolver un
            // refresh nuevo. Guardarlo es obligatorio: el anterior queda
            // blacklisteado y reutilizarlo cerraría la sesión en el próximo
            // vencimiento del access token.
            setTokens({ access: res.data.access, refresh: res.data.refresh });
            return res.data.access;
          })
          .finally(() => {
            refrescando = null;
          });
      }
      const nuevoAccess = await refrescando;
      original.headers.Authorization = `Bearer ${nuevoAccess}`;
      return client(original);
    } catch {
      clearTokens();
      return Promise.reject(error);
    }
  }
);

export default client;
