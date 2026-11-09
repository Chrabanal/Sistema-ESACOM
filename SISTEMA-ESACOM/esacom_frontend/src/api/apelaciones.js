import client from "./client";

export async function fetchApelaciones(params = {}) {
  const { data } = await client.get("/apelaciones/", { params });
  return data.results ?? data;
}

export async function detectarApelaciones() {
  const { data } = await client.post("/apelaciones/detectar/");
  return data;
}

export async function excluirApelacion(id) {
  const { data } = await client.post(`/apelaciones/${id}/excluir/`);
  return data;
}

export async function enviarApelacion(id) {
  const { data } = await client.post(`/apelaciones/${id}/enviar/`);
  return data;
}

/** GET /api/equipo/resumen/ -- cabecera del Portal Supervisor. */
export async function fetchResumenEquipo() {
  const { data } = await client.get("/equipo/resumen/");
  return data;
}

/** POST /api/integraciones/cargar-excel/ (multipart) -- pantalla Cargar Datos. */
export async function cargarExcel(archivo, tipo, metadata = {}) {
  const formData = new FormData();
  formData.append("archivo", archivo);
  formData.append("tipo", tipo);
  Object.entries(metadata).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") formData.append(key, value);
  });
  const { data } = await client.post("/integraciones/cargar-excel/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** GET /api/cargas-excel/ -- historial de cargas. */
export async function fetchHistorialCargas(params = {}) {
  const { data } = await client.get("/cargas-excel/", { params });
  return data.results ?? data;
}

/** GET /api/registros-kpi/ -- auditoría de cruces del KPI. */
export async function fetchRegistrosKPI(params = {}) {
  const { data } = await client.get("/registros-kpi/", { params });
  return data;
}


/** GET /api/registros-kpi/resumen/ -- métricas de auditoría de una carga KPI. */
export async function fetchResumenAuditoriaKPI(params = {}) {
  const { data } = await client.get("/registros-kpi/resumen/", { params });
  return data;
}

/** GET /api/ventas/ -- lista de clientes del equipo, con filtros opcionales. */
export async function fetchVentas(params = {}) {
  const { data } = await client.get("/ventas/", { params });
  return data.results ?? data;
}

/**
 * Igual que fetchVentas pero devuelve el objeto de paginación completo
 * (count/next/previous/results) -- lo usa la pantalla Base de Datos,
 * que necesita mostrar el total y navegar página a página.
 */
export async function fetchVentasPaginado(params = {}) {
  const { data } = await client.get("/ventas/", { params });
  return data;
}

/** POST /api/gestiones/ -- deja constancia de una llamada o WhatsApp. */
export async function registrarGestion(ventaId, tipo, extra = {}) {
  const { data } = await client.post("/gestiones/", { venta_id: ventaId, tipo, ...extra });
  return data;
}

/** GET /api/ventas/{id}/detalle/ -- venta + cortes + historial de gestiones. */
export async function fetchVentaDetalle(id) {
  const { data } = await client.get(`/ventas/${id}/detalle/`);
  return data;
}

/** GET /api/cortes/ -- seguimiento/cobranza con filtros. */
export async function fetchCortes(params = {}) {
  const { data } = await client.get("/cortes/", { params });
  return data.results ?? data;
}

/**
 * Recupera todos los cortes B1 pendientes del período solicitado.
 * Recorre la paginación del backend sin modificar los permisos por usuario.
 */
export async function fetchCortesB1Pendientes(mes) {
  const filas = [];
  let pagina = 1;
  let total = null;

  while (pagina <= 1000) {
    const { data } = await client.get("/cortes/", {
      params: {
        mes_ano: mes,
        boleta: "B1",
        estado_pago: "PENDIENTE",
        page: pagina,
      },
    });

    const bloque = Array.isArray(data) ? data : data.results;

    if (!Array.isArray(bloque)) {
      throw new Error("Respuesta inesperada al consultar cortes B1.");
    }

    filas.push(...bloque);

    if (Array.isArray(data)) break;

    total = data.count ?? null;

    if (!data.next) {
      if (total !== null && filas.length < total) {
        throw new Error("La consulta B1 terminó con registros faltantes.");
      }
      break;
    }

    pagina += 1;
  }

  if (pagina > 1000) {
    throw new Error("Se alcanzó el límite de páginas de cortes B1.");
  }

  return filas;
}

export async function verificarCorte(id, estadoPago) {
  const { data } = await client.post(`/cortes/${id}/verificar/`, { estado_pago: estadoPago });
  return data;
}

export async function descargarApelacionesExcel(params = {}) {
  const response = await client.get("/apelaciones/exportar/", { params, responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const a = document.createElement("a");
  a.href = url; a.download = "APELACIONES_ESACOM.xlsx"; a.click();
  URL.revokeObjectURL(url);
}

/**
 * Descarga todas las ventas que cumplen los filtros, recorriendo la paginación
 * del backend en bloques de 1000. Evita exportaciones truncadas cuando la base
 * supera el límite máximo de una sola página.
 */
export async function fetchTodasVentas(params = {}) {
  const filas = [];
  let page = 1;
  let total = null;
  do {
    const { data } = await client.get("/ventas/", {
      params: { ...params, page, page_size: 1000 },
    });
    const bloque = data.results ?? data;
    filas.push(...bloque);
    total = data.count ?? filas.length;
    if (!data.next || filas.length >= total) break;
    page += 1;
  } while (page <= 1000);
  return filas;
}
