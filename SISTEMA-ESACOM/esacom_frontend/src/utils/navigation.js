import { ADMIN_URL } from "../api/client";

export function menuPorUsuario(user) {
  if (!user) return [];

  const p = user.permisos || {};
  const items = [];

  const add = (permiso, label, to, extra = {}) => {
    if (p[permiso]) items.push({ label, to, permiso, ...extra });
  };

  const addLibre = (label, to, extra = {}) => {
    items.push({ label, to, ...extra });
  };

  switch (user.cargo) {
    case "GERENCIA":
      add("dashboard_gerencia", "Dashboard", "/dashboard");
      add("dashboard_gerencia", "Ejecutivos", "/ejecutivos");
      add("dashboard_gerencia", "Cierres KPI", "/cierres-kpi");
      add("accionables", "Accionables", "/accionables");
      add("cobranza", "Cobranza", "/cobranza");
      add("apelaciones", "Apelaciones", "/apelaciones");
      add("historico", "Histórico", "/historico");
      add("analisis", "Análisis", "/analisis");
      add("auditoria_kpi", "Auditoría KPI", "/auditoria-kpi");
      add("base_datos", "Base de Datos", "/base-datos");
      add("estado_sistema", "Estado sistema", "/estado-sistema");
      add("permisos", "Permisos", "/permisos");
      if (p.dashboard_gerencia) items.push({ label: "Admin", href: ADMIN_URL, permiso: "dashboard_gerencia" });
      break;

    case "OPERACIONES":
      addLibre("Inicio", "/operaciones");
      add("accionables", "Accionables", "/accionables");
      add("apelaciones", "Apelaciones", "/apelaciones");
      add("historico", "Histórico", "/historico");
      add("base_datos", "Base de Datos", "/base-datos");
      add("auditoria_kpi", "Auditoría KPI", "/auditoria-kpi");
      add("analisis", "Análisis", "/analisis");
      break;

    case "CONTABILIDAD":
      addLibre("Inicio", "/contabilidad");
      add("cobranza", "Cobranza", "/cobranza");
      add("historico", "Histórico", "/historico");
      add("auditoria_kpi", "Auditoría KPI", "/auditoria-kpi");
      break;

    case "SUPERVISOR":
      add("mi_equipo", "Mi Equipo", "/supervisor");
      add("accionables", "Accionables", "/accionables");
      break;

    case "EJECUTIVO":
      add("mi_portal", "Mi Portal", "/mi-portal");
      add("accionables", "Accionables", "/accionables");
      break;

    case "SOPORTE":
      add("usuarios", "Usuarios", "/soporte");
      add("cargar_datos", "Carga de Datos", "/cargar-datos");
      add("estado_sistema", "Estado sistema", "/estado-sistema");
      add("permisos", "Permisos", "/permisos");
      break;

    default:
      break;
  }

  return items;
}
