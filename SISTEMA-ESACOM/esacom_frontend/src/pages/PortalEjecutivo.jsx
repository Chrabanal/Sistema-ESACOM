import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import KpiCard from "../components/KpiCard";
import ClienteDetalleModal from "../components/ClienteDetalleModal";
import { UrgenciaBarChart } from "../components/DashboardCharts";
import { fetchAccionables, fetchDashboardKpiCompleto } from "../api/dashboard";
import { fetchVentas, registrarGestion } from "../api/apelaciones";

const ESTADO_BADGE = {
  PENDIENTE_INSTALACION: "bg-orange-50 text-esacom-orange",
  PENDIENTE_COMERCIAL: "bg-purple-50 text-purple-600",
  INSTALADO: "bg-green-50 text-esacom-green",
  ANULADO: "bg-gray-100 text-gray-500",
};

const ESTADO_LABEL = {
  PENDIENTE_INSTALACION: "Pendiente instalación",
  PENDIENTE_COMERCIAL: "Pendiente comercial",
  INSTALADO: "Instalado",
  ANULADO: "Anulado",
};

const NOMBRE_BOLETA = { B1: "1ª boleta", B2: "2ª boleta", B3: "3ª boleta" };

function normalizarBusqueda(valor = "") {
  return String(valor)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function mesCalendario(offset = 0) {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() + offset);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function nombreMes(mesAno = "") {
  const [anio, mes] = String(mesAno).split("-");
  const nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  const i = Number(mes) - 1;
  return i >= 0 && i < 12 ? `${nombres[i]} ${anio}` : mesAno || "Sin mes";
}

function telHref(telefono) {
  return `tel:+56${telefono.replace(/^0+/, "")}`;
}

function whatsappHref(telefono) {
  return `https://wa.me/56${telefono.replace(/^0+/, "")}`;
}

function ClienteCard({ venta, onDetalle, activoPago = false }) {
  const [enviando, setEnviando] = useState(null);

  async function handleClick(tipo, href) {
    setEnviando(tipo);
    try {
      // Solo deja una huella automática del contacto. El Ejecutivo no edita
      // clientes, estados, metas ni datos maestros.
      await registrarGestion(venta.id, tipo);
    } catch {
      // El contacto no debe bloquearse por una falla al guardar auditoría.
    } finally {
      setEnviando(null);
      window.open(href, "_blank");
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900 text-sm leading-snug">{venta.nombre_cliente || venta.rut_cliente}</p>
          <p className="text-xs text-gray-400">{venta.rut_cliente} · {venta.n_pedido}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          {activoPago && <span className="whitespace-nowrap rounded-full bg-green-100 px-2.5 py-1 text-[10px] font-bold text-green-800 sm:text-[11px]">Activo · pagó boleta</span>}
          <span className={`text-[10px] sm:text-[11px] whitespace-nowrap font-semibold px-2.5 py-1 rounded-full ${ESTADO_BADGE[venta.estado_instalacion] || "bg-gray-100 text-gray-500"}`}>
            {ESTADO_LABEL[venta.estado_instalacion] || venta.estado_instalacion}
          </span>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-2">{venta.promocion?.nombre || "Producto sin detalle"}</p>
      <button onClick={() => onDetalle?.(venta.id)} className="mt-3 w-full min-h-11 text-xs font-semibold rounded-xl py-2.5 border border-gray-200 text-gray-700 hover:bg-gray-50 active:scale-[0.99] transition">
        Ver historial / boletas
      </button>

      {venta.telefono_cliente ? (
        <div className="grid grid-cols-2 gap-2 mt-3">
          <button onClick={() => handleClick("LLAMADA", telHref(venta.telefono_cliente))} disabled={enviando === "LLAMADA"} className="min-h-11 text-xs font-semibold rounded-xl py-2.5 bg-green-50 text-esacom-green hover:bg-green-100 transition-colors disabled:opacity-60">
            📞 Llamar
          </button>
          <button onClick={() => handleClick("WHATSAPP", whatsappHref(venta.telefono_cliente))} disabled={enviando === "WHATSAPP"} className="min-h-11 text-xs font-semibold rounded-xl py-2.5 bg-green-50 text-esacom-green hover:bg-green-100 transition-colors disabled:opacity-60">
            WhatsApp
          </button>
        </div>
      ) : <p className="text-[11px] text-gray-300 mt-3">Sin teléfono registrado</p>}
    </div>
  );
}

function IndicadorPrincipal({ label, valor, detalle, tono = "azul" }) {
  const tonos = {
    azul: "bg-blue-50 border-blue-100 text-blue-700",
    verde: "bg-green-50 border-green-100 text-green-700",
    lima: "bg-esacom-lime-light border-esacom-lime/30 text-esacom-ink",
  };
  return (
    <div className={`rounded-2xl border p-4 ${tonos[tono] || tonos.azul}`}>
      <p className="text-[10px] uppercase tracking-wide font-bold opacity-75">{label}</p>
      <p className="mt-1 text-2xl font-extrabold tracking-tight">{valor}</p>
      <p className="mt-1 text-[11px] leading-snug opacity-75">{detalle}</p>
    </div>
  );
}

function HistoricoCard({ corte }) {
  const cierreOficial = corte.cierre_oficial === true || corte.estado_medicion === "CIERRE";
  const cerrado = corte.estado_mes === "CERRADO" || cierreOficial;
  const esHonorarios = corte.perfil_kpi === "HONORARIOS" || corte.meta_definida === false;
  const esCierreFijo = corte.fuente_formato === "CIERRE_FIJO";
  const estadoLabel = cierreOficial ? (esCierreFijo ? "CIERRE OFICIAL FIJO" : "CIERRE OFICIAL") : cerrado ? "FINALIZADO" : "ÚLTIMO AVANCE";
  const tieneMeta = !esHonorarios && Number(corte.meta_pct || 0) > 0;
  const cumple = tieneMeta && Number(corte.pct_cumplimiento || 0) >= Number(corte.meta_pct || 0);
  const colorKpi = esHonorarios ? "text-blue-700" : cumple ? "text-green-700" : "text-red-700";
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold text-gray-900">{nombreMes(corte.mes_ano)}</p>
            <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${cierreOficial ? "bg-green-50 text-green-700" : cerrado ? "bg-gray-100 text-gray-600" : "bg-blue-50 text-blue-700"}`}>{estadoLabel}</span>
          </div>
          <p className="text-xs text-gray-500">Referencia {NOMBRE_BOLETA[corte.boleta] || corte.boleta}</p>
          {(corte.dia_reporte || corte.fecha_corte) && <p className="mt-1 text-[10px] text-gray-400">{corte.dia_reporte || "Reporte"}{corte.fecha_corte ? ` · corte ${corte.fecha_corte}` : ""}</p>}
        </div>
        <div className="text-right">
          <p className={`text-xl font-extrabold ${colorKpi}`}>{Number(corte.pct_cumplimiento || 0).toFixed(2)}%</p>
          {tieneMeta ? (
            <>
              <p className="text-[10px] text-gray-500">Meta ESACOM {Number(corte.meta_pct || 0).toFixed(0)}%</p>
              <p className={`mt-1 text-[10px] font-bold ${cumple ? "text-green-700" : "text-red-700"}`}>{cumple ? "Cumplió" : "No cumplió"}</p>
            </>
          ) : (
            <><p className="text-[10px] text-gray-500">Meta Honorarios pendiente</p><p className="mt-1 text-[10px] font-bold text-blue-700">KPI de pago</p></>
          )}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
        <div className="rounded-xl bg-green-50 p-2"><p className="text-[9px] text-green-700">Pago</p><p className="font-bold text-green-800">{corte.pagadas || 0}</p></div>
        <div className="rounded-xl bg-blue-50 p-2"><p className="text-[9px] text-blue-700">Pendiente</p><p className="font-bold text-blue-800">{corte.pendientes || 0}</p></div>
        <div className="rounded-xl bg-red-50 p-2"><p className="text-[9px] text-red-700">No pago</p><p className="font-bold text-red-800">{corte.no_pago || 0}</p></div>
        <div className="rounded-xl bg-gray-50 p-2"><p className="text-[9px] text-gray-500">Total RGU</p><p className="font-bold text-gray-800">{corte.total || 0}</p></div>
      </div>
      <div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] text-gray-400">
        <span>Fuera plazo {corte.fuera_plazo || 0} · S/B {corte.sin_boleta || 0} · Fuera medición {corte.fuera_medicion || 0}</span>
        {corte.valor_informado_claro !== null && corte.valor_informado_claro !== undefined && <span>{corte.cierre_oficial ? "Cierre oficial Claro" : "Última referencia Claro"}: {Number(corte.valor_informado_claro).toFixed(2)}%</span>}
      </div>
    </div>
  );
}

export default function PortalEjecutivo() {
  const [tab, setTab] = useState("kpi");
  const [cortes, setCortes] = useState(null);
  const [historicoKpi, setHistoricoKpi] = useState([]);
  const [perfilKpi, setPerfilKpi] = useState("REGULAR");
  const [honorarios, setHonorarios] = useState(null);
  const [produccionMes, setProduccionMes] = useState(null);
  const [resumenMes, setResumenMes] = useState(null);
  const [mesActual, setMesActual] = useState(mesCalendario(0));
  const [mesAnterior, setMesAnterior] = useState(mesCalendario(-1));
  const [clientesActuales, setClientesActuales] = useState(null);
  const [clientesAnteriores, setClientesAnteriores] = useState(null);
  const [clientesActivosActuales, setClientesActivosActuales] = useState(null);
  const [clientesActivosAnteriores, setClientesActivosAnteriores] = useState(null);
  const [mesClientes, setMesClientes] = useState("ACTUAL");
  const [filtroClientes, setFiltroClientes] = useState("GESTIONABLES");
  const [busqueda, setBusqueda] = useState("");
  const [error, setError] = useState("");
  const [ventaDetalle, setVentaDetalle] = useState(null);
  const [actualizando, setActualizando] = useState(false);
  const [accionables, setAccionables] = useState(null);

  const cargarDashboard = useCallback(async ({ silencioso = false } = {}) => {
    if (!silencioso) setActualizando(true);
    try {
      const [data, acc] = await Promise.all([fetchDashboardKpiCompleto(), fetchAccionables()]);
      setAccionables(acc || null);
      setCortes(data.cortes || []);
      setHistoricoKpi(data.historico_kpi || []);
      setPerfilKpi(data.perfil_kpi || "REGULAR");
      setHonorarios(data.honorarios || null);
      setProduccionMes(data.produccion_mes_actual || null);
      setResumenMes(data.resumen_mes_actual || null);
      if (data.mes_actual) setMesActual(data.mes_actual);
      if (data.mes_anterior) setMesAnterior(data.mes_anterior);
      setError("");
    } catch {
      if (!silencioso) setError("No se pudo actualizar tu información.");
    } finally {
      if (!silencioso) setActualizando(false);
    }
  }, []);

  const cargarClientes = useCallback(async (actual, anterior) => {
    try {
      const [a, b] = await Promise.all([
        fetchVentas({ camada: actual, page_size: 1000 }),
        fetchVentas({ camada: anterior, page_size: 1000 }),
      ]);
      setClientesActuales(a || []);
      setClientesAnteriores(b || []);
    } catch {
      setError("No se pudieron cargar tus clientes del mes actual y anterior.");
    }
  }, []);

  const cargarClientesActivos = useCallback(async (actual, anterior, cortesVigentes) => {
    const porMes = new Map((cortesVigentes || []).map((c) => [c.mes_ano, c.boleta]));
    const boletaActual = porMes.get(actual);
    const boletaAnterior = porMes.get(anterior);
    try {
      const [activosA, activosB] = await Promise.all([
        boletaActual ? fetchVentas({ activo_pago_mes: actual, activo_pago_boleta: boletaActual, page_size: 1000 }) : Promise.resolve([]),
        boletaAnterior ? fetchVentas({ activo_pago_mes: anterior, activo_pago_boleta: boletaAnterior, page_size: 1000 }) : Promise.resolve([]),
      ]);
      setClientesActivosActuales(activosA || []);
      setClientesActivosAnteriores(activosB || []);
    } catch {
      setClientesActivosActuales([]);
      setClientesActivosAnteriores([]);
      setError("No se pudieron cargar los clientes activos por pago.");
    }
  }, []);

  useEffect(() => {
    cargarDashboard();
    const timer = window.setInterval(() => cargarDashboard({ silencioso: true }), 60_000);
    const onFocus = () => cargarDashboard({ silencioso: true });
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [cargarDashboard]);

  useEffect(() => {
    setClientesActuales(null);
    setClientesAnteriores(null);
    cargarClientes(mesActual, mesAnterior);
  }, [cargarClientes, mesActual, mesAnterior]);

  useEffect(() => {
    setClientesActivosActuales(null);
    setClientesActivosAnteriores(null);
    if (cortes !== null) cargarClientesActivos(mesActual, mesAnterior, cortes);
  }, [cargarClientesActivos, cortes, mesActual, mesAnterior]);

  async function actualizarTodo() {
    setActualizando(true);
    try {
      await Promise.all([cargarDashboard({ silencioso: true }), cargarClientes(mesActual, mesAnterior)]);
      setError("");
    } catch {
      setError("No se pudo actualizar la información en este momento.");
    } finally {
      setActualizando(false);
    }
  }

  const clientesMes = mesClientes === "ACTUAL" ? clientesActuales : clientesAnteriores;
  const clientesActivosMes = mesClientes === "ACTUAL" ? clientesActivosActuales : clientesActivosAnteriores;
  const mesSeleccionado = mesClientes === "ACTUAL" ? mesActual : mesAnterior;
  const boletaActivaMes = (cortes || []).find((c) => c.mes_ano === mesSeleccionado)?.boleta || null;
  const q = normalizarBusqueda(busqueda);

  const clientesFiltrados = useMemo(() => {
    const base = filtroClientes === "ACTIVOS_PAGO" ? (clientesActivosMes || []) : (clientesMes || []);
    return base.filter((venta) => {
      if (filtroClientes === "GESTIONABLES" && venta.estado_instalacion === "ANULADO") return false;
      if (!["GESTIONABLES", "ACTIVOS_PAGO"].includes(filtroClientes) && venta.estado_instalacion !== filtroClientes) return false;
      if (!q) return true;
      const texto = normalizarBusqueda([venta.nombre_cliente, venta.rut_cliente].filter(Boolean).join(" "));
      return q.split(/\s+/).every((parte) => texto.includes(parte));
    });
  }, [clientesMes, clientesActivosMes, filtroClientes, q]);

  const resultadosBusqueda = useMemo(() => {
    if (q.length < 2) return [];
    const mapa = new Map();
    [
      ...(clientesActuales || []), ...(clientesAnteriores || []),
      ...(clientesActivosActuales || []), ...(clientesActivosAnteriores || []),
    ].forEach((venta) => {
      const texto = normalizarBusqueda(`${venta.nombre_cliente || ""} ${venta.rut_cliente || ""}`);
      if (q.split(/\s+/).every((parte) => texto.includes(parte))) mapa.set(venta.id, venta);
    });
    return [...mapa.values()].slice(0, 8);
  }, [q, clientesActuales, clientesAnteriores, clientesActivosActuales, clientesActivosAnteriores]);

  const cortePrincipal = (cortes || [])[0];
  const mesCalidadPendiente = cortePrincipal?.mes_ano && mesActual > cortePrincipal.mes_ano ? mesActual : null;
  const completadas = (clientesActuales || []).filter((v) => v.estado_instalacion === "INSTALADO");
  const kpiCalidad = Number(cortePrincipal?.pct_cumplimiento || 0);
  const metaCalidad = Number(cortePrincipal?.meta_pct || 0);
  const tieneMetaCalidad = cortePrincipal?.meta_definida !== false && metaCalidad > 0;
  const cumpleCalidad = cortePrincipal?.tiene_datos !== false && tieneMetaCalidad && kpiCalidad >= metaCalidad;
  const rguFijoVendidos = produccionMes?.rgu_fijo_vendidos ?? produccionMes?.fija?.rgu_total_base_vigente ?? produccionMes?.kpi_fijo_rgu ?? 0;
  const rguFijoGestionables = produccionMes?.rgu_fijo_gestionables ?? produccionMes?.fija?.total_control ?? 0;
  const ventasFijo = produccionMes?.ventas_fijo ?? produccionMes?.fija?.total_base_vigente ?? 0;
  const rguFijoAnulados = produccionMes?.rgu_fijo_anulados ?? produccionMes?.fija?.anuladas ?? 0;

  return (
    <Layout titulo="Mi Portal" items={[{ label: "Accionables", to: "/accionables" }]}>
      <section className="mb-5 rounded-3xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm" aria-label="Buscar mis clientes">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-extrabold text-esacom-ink">Busca tus clientes</h2>
            <p className="mt-1 text-xs text-gray-500">Escribe el RUT o el nombre. Busca en tu cartera del mes actual/anterior e incluye clientes activos por pago.</p>
          </div>
          <button type="button" onClick={actualizarTodo} disabled={actualizando} className="shrink-0 rounded-xl border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            {actualizando ? "Actualizando…" : "↻ Actualizar"}
          </button>
        </div>
        <div className="relative mt-4">
          <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar por RUT o nombre…" className="w-full min-h-12 rounded-2xl border border-gray-200 bg-gray-50 px-4 pr-10 text-sm outline-none focus:border-esacom-lime focus:ring-2 focus:ring-esacom-lime/20" />
          {busqueda && <button type="button" aria-label="Limpiar búsqueda" onClick={() => setBusqueda("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">✕</button>}
        </div>
        {q.length >= 2 && (
          <div className="mt-2 overflow-hidden rounded-2xl border border-gray-200 bg-white">
            {resultadosBusqueda.length === 0 ? <p className="p-4 text-xs text-gray-400">No encontramos clientes con ese RUT o nombre en estos dos meses.</p> : resultadosBusqueda.map((v) => (
              <button key={v.id} type="button" onClick={() => setVentaDetalle(v.id)} className="flex w-full items-center justify-between gap-3 border-b border-gray-100 px-4 py-3 text-left last:border-0 hover:bg-gray-50">
                <div><p className="text-xs font-semibold text-gray-900">{v.nombre_cliente || v.rut_cliente}</p><p className="text-[11px] text-gray-400">{v.rut_cliente} · {nombreMes(v.camada)}</p></div>
                <span className="text-[11px] font-semibold text-esacom-blue">Ver</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="mb-5" aria-labelledby="resumen-actual">
          <div className="mb-3">
            <h2 id="resumen-actual" className="text-lg font-extrabold tracking-tight text-esacom-ink">Resumen actual</h2>
            <p className="text-xs text-gray-500">Tus ventas vienen de ESACOM. Calidad se actualiza con los reportes de Claro y puede venir un mes desfasada.</p>
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <IndicadorPrincipal
              label={`${perfilKpi === "HONORARIOS" ? "Calidad de pago Honorarios" : "Calidad de pago"} · ${cortePrincipal ? nombreMes(cortePrincipal.mes_ano) : "Sin medición"}`}
              valor={!cortePrincipal || cortePrincipal?.tiene_datos === false ? "Sin datos" : `${kpiCalidad.toFixed(2)}%`}
              detalle={cortePrincipal ? (perfilKpi === "HONORARIOS" ? "KPI real de pago · Meta Honorarios pendiente" : `${cumpleCalidad ? "✓ Cumples" : "Aún no cumples"} · Meta ESACOM ${metaCalidad.toFixed(0)}%`) : "Claro aún no entrega una medición vigente"}
              tono="azul"
            />
            <IndicadorPrincipal
              label={`Ventas Fijo · ${nombreMes(mesActual)} · ESACOM`}
              valor={`${rguFijoVendidos} RGU vendidos`}
              detalle={`${ventasFijo} ventas · ${rguFijoGestionables} gestionables · ${rguFijoAnulados} RGU ${rguFijoAnulados === 1 ? "anulado" : "anulados"}`}
              tono="verde"
            />
            <IndicadorPrincipal
              label={`Ventas Móvil · ${nombreMes(mesActual)} · ESACOM`}
              valor={`${produccionMes?.kpi_movil_portadas ?? 0} portadas`}
              detalle={`Principal ${produccionMes?.movil?.principal ?? 0} · Adicional ${produccionMes?.movil?.adicional ?? 0}`}
              tono="lima"
            />
          </div>
          <div className="mt-3 flex flex-col gap-1 rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-[11px] text-blue-800 sm:flex-row sm:items-center sm:justify-between">
            <span><strong>{nombreMes(mesActual)}</strong>: ventas y RGU actuales según la base oficial ESACOM.</span>
            <span><strong>{cortePrincipal ? nombreMes(cortePrincipal.mes_ano) : "Calidad"}</strong>: período que Claro está midiendo actualmente.</span>
          </div>
        </section>

      {resumenMes && (
        <section className="mb-5 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm" aria-label="Resumen del mes actual">
          <div className="flex items-center justify-between gap-3">
            <div><p className="text-sm font-bold text-gray-900">Actividad · {nombreMes(resumenMes.mes || mesActual)}</p><p className="text-[11px] text-gray-500">Solo ventas y clientes del mes actual.</p></div>
            <span className="rounded-full bg-esacom-lime-light px-3 py-1 text-xs font-bold text-esacom-ink">{resumenMes.avance_instalacion_pct || 0}% instalación</span>
          </div>
          <div className="mt-3 grid grid-cols-4 gap-2 text-center">
            {[["Ventas", resumenMes.total], ["Instaladas", resumenMes.instaladas], ["Pend. inst.", resumenMes.pendiente_instalacion], ["Pend. com.", resumenMes.pendiente_comercial]].map(([l, v]) => (
              <div key={l} className="rounded-xl bg-gray-50 px-2 py-3"><p className="text-lg font-extrabold text-gray-900">{v || 0}</p><p className="text-[9px] text-gray-500">{l}</p></div>
            ))}
          </div>
        </section>
      )}

      {perfilKpi !== "HONORARIOS" && accionables && (
        <section className="mb-5 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm" aria-label="Prioridades de gestión">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-extrabold text-gray-900">Qué atender ahora</p>
              <p className="mt-1 text-[11px] text-gray-500">Tus pendientes de Calidad del período en curso, ordenados por vencimiento.</p>
            </div>
            <a href="/accionables" className="inline-flex min-h-10 items-center justify-center rounded-xl bg-gray-900 px-4 text-xs font-semibold text-white">Gestionar ahora →</a>
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
              {[
                ["Vencidos", accionables.vencidos, "bg-red-50 text-red-800"],
                ["Hoy", accionables.hoy, "bg-orange-50 text-orange-800"],
                ["Mañana", accionables.manana, "bg-yellow-50 text-yellow-800"],
                ["Próx. 3 días", accionables.prox_3d, "bg-blue-50 text-blue-800"],
              ].map(([label, dato, clase]) => (
                <div key={label} className={`rounded-xl p-3 ${clase}`}>
                  <p className="text-[10px] font-bold uppercase opacity-70">{label}</p>
                  <p className="mt-1 text-xl font-extrabold">{dato?.clientes || 0} <span className="text-xs font-semibold">clientes</span></p>
                  <p className="mt-1 text-[10px] opacity-70">{dato?.rgu || 0} RGU · {dato?.casos || 0} casos</p>
                </div>
              ))}
            </div>
            <UrgenciaBarChart
              titulo="Prioridad visual"
              subtitulo="RGU por vencimiento para decidir dónde actuar primero."
              items={[
                { name: "Vencidos", value: accionables.vencidos?.rgu },
                { name: "Hoy", value: accionables.hoy?.rgu },
                { name: "Mañana", value: accionables.manana?.rgu },
                { name: "Próx. 3 días", value: accionables.prox_3d?.rgu },
              ]}
            />
          </div>
        </section>
      )}

      <div className="sticky top-[57px] z-20 -mx-3 mb-4 bg-gray-50/95 px-3 py-2 backdrop-blur sm:static sm:mx-0 sm:bg-transparent sm:px-0 sm:py-0 sm:backdrop-blur-0">
        <div className="grid grid-cols-4 gap-1 rounded-2xl border border-gray-200 bg-white p-1 shadow-sm sm:border-0 sm:bg-transparent sm:shadow-none">
          {[["kpi", "Mi KPI"], ["clientes", "Mis Clientes"], ["historico", "Histórico"], ["completadas", "Completadas"]].map(([key, label]) => (
            <button key={key} onClick={() => setTab(key)} className={`rounded-xl px-1.5 py-2.5 text-[11px] transition-colors sm:px-4 sm:text-sm ${tab === key ? "bg-esacom-lime-light font-semibold text-esacom-ink" : "text-gray-500 hover:text-esacom-ink"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="mb-4 rounded-lg bg-esacom-red-light px-4 py-3 text-sm text-esacom-red">{error}</p>}

      {tab === "kpi" && (
        <>
          {cortes === null && <div className="h-48 animate-pulse rounded-xl bg-gray-100" />}
          {cortes && (
            <div>
              <div className="mb-3">
                <h2 className="text-base font-extrabold text-gray-900">{perfilKpi === "HONORARIOS" ? "KPI Calidad Honorarios en curso" : "KPI Calidad en curso"}</h2>
                <p className="text-xs text-gray-500">{perfilKpi === "HONORARIOS" ? "Se muestra el porcentaje real de pago informado por Claro. La meta Honorarios permanece separada y pendiente de definición por Gerencia." : "Solo el mes actualmente medido por Claro permanece abierto. Los meses anteriores quedan congelados en Histórico."}</p>
              </div>
              {perfilKpi === "HONORARIOS" && (
                <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <p className="text-xs font-bold text-amber-900">Perfil Honorarios · medición independiente del KPI Regular</p>
                  <p className="mt-1 text-[11px] text-amber-800">No se aplica la meta 85/83/80 ni se informa Cumple/No cumple hasta que Gerencia defina la meta Honorarios. Tus ventas actuales siguen viniendo de ESACOM.</p>
                </div>
              )}
              {mesCalidadPendiente && (
                <div className="mb-4 rounded-2xl border border-dashed border-blue-200 bg-blue-50/50 px-4 py-3">
                  <p className="text-xs font-bold text-blue-800">{nombreMes(mesCalidadPendiente)} · aún sin medición de Calidad</p>
                  <p className="mt-1 text-[11px] text-blue-700/80">La producción del mes ya se muestra arriba, pero el KPI Calidad aparecerá cuando Claro entregue la medición correspondiente.</p>
                </div>
              )}
              <div className="max-w-2xl">{cortes.length ? cortes.map((c) => <KpiCard key={`${c.mes_ano}-${c.boleta}`} corte={c} />) : <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">Aún no existe una medición de Calidad en curso para tu cartera.</div>}</div>
            </div>
          )}
        </>
      )}

      {tab === "clientes" && (
        <>
          <div className="mb-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div><p className="text-sm font-bold text-gray-900">Mis clientes · {nombreMes(mesSeleccionado)}</p><p className="text-xs text-gray-500">Mes actual por defecto. “Activos por pago” muestra quienes pagaron la boleta vigente de ese mes{boletaActivaMes ? ` (${NOMBRE_BOLETA[boletaActivaMes]})` : ""}.</p></div>
              <div className="flex rounded-xl bg-gray-100 p-1">
                <button type="button" onClick={() => setMesClientes("ACTUAL")} className={`rounded-lg px-3 py-2 text-xs font-semibold ${mesClientes === "ACTUAL" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"}`}>Mes actual</button>
                <button type="button" onClick={() => setMesClientes("ANTERIOR")} className={`rounded-lg px-3 py-2 text-xs font-semibold ${mesClientes === "ANTERIOR" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"}`}>Mes anterior</button>
              </div>
            </div>
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {[["ACTIVOS_PAGO", `Activos por pago (${(clientesActivosMes || []).length})`], ["GESTIONABLES", "Gestionables"], ["INSTALADO", "Instalados"], ["PENDIENTE_INSTALACION", "Pend. instalación"], ["PENDIENTE_COMERCIAL", "Pend. comercial"], ["ANULADO", "Anulados"]].map(([valor, label]) => (
                <button key={valor} type="button" onClick={() => setFiltroClientes(valor)} className={`min-h-10 whitespace-nowrap rounded-full border px-3.5 text-xs font-semibold ${filtroClientes === valor ? "border-esacom-ink bg-esacom-ink text-white ring-2 ring-esacom-lime/20" : "border-gray-200 bg-white text-gray-600"}`}>{label}</button>
              ))}
            </div>
          </div>
          {(filtroClientes === "ACTIVOS_PAGO" ? clientesActivosMes : clientesMes) === null ? <div className="h-64 animate-pulse rounded-2xl bg-gray-100" /> : clientesFiltrados.length === 0 ? <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">No hay clientes que coincidan con este mes, estado o búsqueda.</div> : <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{clientesFiltrados.map((v) => <ClienteCard key={v.id} venta={v} onDetalle={setVentaDetalle} activoPago={filtroClientes === "ACTIVOS_PAGO"} />)}</div>}
        </>
      )}

      {tab === "historico" && (
        <section>
          <div className="mb-3"><h2 className="text-base font-extrabold text-gray-900">{perfilKpi === "HONORARIOS" ? "Histórico KPI Calidad Honorarios" : "Histórico KPI Calidad Fijo"}</h2><p className="text-xs text-gray-500">{perfilKpi === "HONORARIOS" ? "Muestra tu porcentaje real de pago por mes, sin aplicar una meta Regular. Los cierres quedan congelados." : "Muestra un resultado por mes. Cuando el mes deja de estar en curso queda congelado y no cambia porque aparezca después como otra boleta en un reporte de Claro."}</p></div>
          {historicoKpi.length === 0 ? <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">Todavía no hay boletas anteriores disponibles para tu cartera.</div> : <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{historicoKpi.map((c, i) => <HistoricoCard key={`${c.mes_ano}-${c.boleta}-${i}`} corte={c} />)}</div>}
        </section>
      )}

      {tab === "completadas" && (
        <section>
          <div className="mb-3"><h2 className="text-base font-extrabold text-gray-900">Completadas · {nombreMes(mesActual)}</h2><p className="text-xs text-gray-500">Solo instalaciones completadas del mes actual.</p></div>
          {clientesActuales === null ? <div className="h-64 animate-pulse rounded-xl bg-gray-100" /> : completadas.length === 0 ? <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-400">Todavía no tienes instalaciones completadas este mes.</div> : <div className="space-y-2">{completadas.map((v) => <div key={v.id} className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-gray-900">{v.nombre_cliente || v.rut_cliente}</p><p className="text-xs text-gray-400">{v.promocion?.nombre || "—"} · {v.fecha_cierre || "—"}</p></div><span className="rounded-full bg-green-50 px-2 py-1 text-[11px] font-medium text-esacom-green">Instalado</span></div>)}</div>}
        </section>
      )}

      <ClienteDetalleModal ventaId={ventaDetalle} onClose={() => setVentaDetalle(null)} permitirGestion={false} />
    </Layout>
  );
}
