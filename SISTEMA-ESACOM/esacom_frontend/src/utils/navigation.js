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
      add("historico", "Histórico", "/historico");
      add("analisis", "Análisis", "/analisis");

      add("accionables", "Accionables", "/accionables", { secundario: true });
      add("cobranza", "Cobranza", "/cobranza", { secundario: true });
      add("apelaciones", "Apelaciones", "/apelaciones", { secundario: true });
      add("auditoria_kpi", "Auditoría KPI", "/auditoria-kpi", { secundario: true });
      add("base_datos", "Base de Datos", "/base-datos", { secundario: true });
      add("estado_sistema", "Estado sistema", "/estado-sistema", { secundario: true });
      add("permisos", "Permisos", "/permisos", { secundario: true });

      if (p.dashboard_gerencia) {
        items.push({
          label: "Admin",
          href: ADMIN_URL,
          permiso: "dashboard_gerencia",
          secundario: true,
        });
      }
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
