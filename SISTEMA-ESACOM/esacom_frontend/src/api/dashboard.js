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
