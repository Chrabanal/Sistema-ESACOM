import client from "./client";

/** GET /api/dashboard/kpi/ -- desglose por corte, ya filtrado por rol en el backend. */
export async function fetchDashboardKpi() {
  const { data } = await client.get("/dashboard/kpi/");
  return data.cortes;
}

/** Mismo endpoint, incluyendo metadata del último snapshot lunes/miércoles. */
export async function fetchDashboardKpiCompleto() {
  const { data } = await client.get("/dashboard/kpi/");
  return data;
}

/** GET /api/dashboard/kpi-ejecutivos/ -- matriz Ejecutivo × Mes × Corte (Gerencia/Supervisor). */
export async function fetchKpiPorEjecutivo() {
  const { data } = await client.get("/dashboard/kpi-ejecutivos/");
  return data.ejecutivos;
}

/** KPI Supervisor: incluye snapshot/focos además de ejecutivos. */
export async function fetchKpiPorEjecutivoCompleto() {
  const { data } = await client.get("/dashboard/kpi-ejecutivos/");
  return data;
}

/** GET /api/dashboard/accionables/ -- Seguimiento Accionables (Hoy/Mañana/Próx. 3 días). */
export async function fetchAccionables() {
  const { data } = await client.get("/dashboard/accionables/");
  return data;
}

/** GET /api/dashboard/historico/ -- comparativo mes a mes de ventas y estado de pago. */
export async function fetchHistorico() {
  const { data } = await client.get("/dashboard/historico/");
  return data.camadas;
}

/** GET /api/dashboard/gerencia/ -- resumen ejecutivo global validado contra ESACOM. */
export async function fetchDashboardGerencia() {
  const { data } = await client.get("/dashboard/gerencia/");
  return data;
}
/** Busca usuarios comerciales para la ficha KPI de Gerencia. */
export async function buscarUsuarioGerencia(q) {
  const { data } = await client.get("/dashboard/gerencia/usuarios/", { params: { q } });
  return data.resultados || [];
}

/** KPI actual, producción actual e histórico del usuario seleccionado. */
export async function fetchUsuarioGerenciaDetalle(id) {
  const { data } = await client.get(`/dashboard/gerencia/usuarios/${id}/`);
  return data;
}


/** Período abierto e histórico de cierres oficiales Claro por canal. */
export async function fetchCierresKpiGerencia(canal = "FIJO") {
  const { data } = await client.get("/dashboard/gerencia/cierres/", { params: { canal } });
  return data;
}

/** Desglose congelado de un cierre oficial mensual. */
export async function fetchCierreKpiGerenciaDetalle(canal, mes) {
  const { data } = await client.get(`/dashboard/gerencia/cierres/${canal}/${mes}/`);
  return data;
}

/** Descarga CSV de resumen o detalle del cierre oficial. */
export async function descargarCierreKpiCsv(canal, mes, tipo = "resumen") {
  const response = await client.get(`/dashboard/gerencia/cierres/${canal}/${mes}/csv/`, {
    params: { tipo },
    responseType: "blob",
  });
  const blob = new Blob([response.data], { type: "text/csv;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `CIERRE_KPI_${canal}_${mes}_${tipo}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
