export function menuPorUsuario(user) {
  if (!user) return [];
  const p = user.permisos || {};
  const items = [];
  const add = (permiso, label, to) => { if (p[permiso]) items.push({ label, to }); };

  switch (user.cargo) {
    case "GERENCIA":
      items.push({ label: "Inicio", to: "/dashboard" });
      add("estado_sistema", "Estado sistema", "/estado-sistema");
      add("accionables", "Accionables", "/accionables");
      add("cobranza", "Cobranza", "/cobranza");
      add("apelaciones", "Apelaciones", "/apelaciones");
      add("historico", "Histórico", "/historico");
      add("analisis", "Análisis", "/analisis");
      add("auditoria_kpi", "Auditoría KPI", "/auditoria-kpi");
      add("base_datos", "Base de Datos", "/base-datos");
      add("permisos", "Permisos", "/permisos");
      break;
    case "OPERACIONES":
      items.push({ label: "Inicio", to: "/operaciones" });
      add("accionables", "Accionables", "/accionables");
      add("apelaciones", "Apelaciones", "/apelaciones");
      add("historico", "Histórico", "/historico");
      add("base_datos", "Base de Datos", "/base-datos");
      add("auditoria_kpi", "Auditoría KPI", "/auditoria-kpi");
      add("analisis", "Análisis", "/analisis");
      break;
    case "CONTABILIDAD":
      items.push({ label: "Inicio", to: "/contabilidad" });
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
