import client from "./client";

export async function fetchUsuarios(params = {}) {
  const { data } = await client.get("/soporte/usuarios/", { params: { page_size: 200, ...params } });
  return data;
}

export async function descargarInformeAccesos(params = {}) {
  const respuesta = await client.get(
    "/soporte/usuarios/descargar-accesos/",
    {
      params,
      responseType: "blob",
    }
  );

  const url = window.URL.createObjectURL(respuesta.data);
  const enlace = document.createElement("a");

  enlace.href = url;
  enlace.download = "esacom_ultimos_accesos.csv";
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();

  window.setTimeout(() => {
    window.URL.revokeObjectURL(url);
  }, 1000);
}

export async function fetchResumenUsuarios() {
  const { data } = await client.get("/soporte/usuarios/resumen/");
  return data;
}

export async function crearUsuario(payload) {
  const { data } = await client.post("/soporte/usuarios/", payload);
  return data;
}

export async function editarUsuario(id, payload) {
  const { data } = await client.patch(`/soporte/usuarios/${id}/`, payload);
  return data;
}

export async function activarUsuario(id) {
  const { data } = await client.post(`/soporte/usuarios/${id}/activar/`);
  return data;
}

export async function desactivarUsuario(id) {
  const { data } = await client.post(`/soporte/usuarios/${id}/desactivar/`);
  return data;
}

export async function resetPassword(id, password = "") {
  const { data } = await client.post(`/soporte/usuarios/${id}/reset-password/`, password ? { password } : {});
  return data;
}

export async function fetchAuditoria(params = {}) {
  const { data } = await client.get("/soporte/auditoria/", { params: { page_size: 100, ...params } });
  return data;
}


export async function fetchPermisosUsuarios() {
  const { data } = await client.get("/permisos/usuarios/");
  return data;
}
export async function configurarPermisos(id, permisos, motivo) {
  const { data } = await client.patch(`/permisos/usuarios/${id}/configurar/`, { permisos, motivo });
  return data;
}
export async function restablecerPermisos(id) {
  const { data } = await client.post(`/permisos/usuarios/${id}/restablecer/`);
  return data;
}

export async function fetchDotacion(params = {}) {
  const { data } = await client.get("/soporte/usuarios/dotacion/", { params });
  return data;
}


export async function sincronizarGoogleSheets() {
  const { data } = await client.post("/integraciones/sincronizar-google-sheets/");
  return data;
}

export async function fetchMetasKpiCalidad() {
  const { data } = await client.get("/soporte/metas-kpi-calidad/");
  return data;
}

export async function crearMetaKpiCalidad(payload) {
  const { data } = await client.post("/soporte/metas-kpi-calidad/", payload);
  return data;
}
