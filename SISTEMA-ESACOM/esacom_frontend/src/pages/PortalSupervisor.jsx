import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import ClienteDetalleModal from "../components/ClienteDetalleModal";
import { EstadoVentasDonut, RankingKpiBarChart, TendenciaKpiChart, UrgenciaBarChart } from "../components/DashboardCharts";
import { fetchResumenEquipo, fetchVentas } from "../api/apelaciones";
import { fetchDashboardKpiCompleto, fetchKpiPorEjecutivoCompleto } from "../api/dashboard";

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "PENDIENTE_INSTALACION", label: "Pendiente instalación" },
  { value: "PENDIENTE_COMERCIAL", label: "Pendiente comercial" },
  { value: "INSTALADO", label: "Instalado" },
  { value: "ANULADO", label: "Anulado" },
];

const ESTADO_BADGE = {
  PENDIENTE_INSTALACION: "bg-orange-50 text-esacom-orange",
  PENDIENTE_COMERCIAL: "bg-purple-50 text-purple-600",
  INSTALADO: "bg-green-50 text-esacom-green",
  ANULADO: "bg-gray-100 text-gray-500",
};

function nombreMes(mesAno = "") {
  const [anio, mes] = String(mesAno || "").split("-");
  const nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
  const i = Number(mes) - 1;
  return i >= 0 && i < 12 ? `${nombres[i]} ${anio}` : mesAno || "Mes actual";
}

function fechaHora(valor) {
  if (!valor) return "Sin carga registrada";
  return new Intl.DateTimeFormat("es-CL", { dateStyle: "short", timeStyle: "short" }).format(new Date(valor));
}

function corteActual(fila) {
  return (fila?.cortes || []).find((c) => c.boleta === "B1") || (fila?.cortes || [])[0] || null;
}

function claseKpi(corte) {
  if (!corte) return "text-gray-300";
  const kpi = Number(corte.pct_cumplimiento || 0);
  const meta = Number(corte.meta_pct || 0);
  if (meta && kpi >= meta) return "text-green-700";
  if (meta && kpi >= meta - 10) return "text-amber-600";
  return "text-esacom-red";
}

function TarjetaResumen({ titulo, valor, detalle, tono = "neutro" }) {
  const tonos = {
    verde: "border-green-100 bg-green-50 text-green-800",
    azul: "border-blue-100 bg-blue-50 text-blue-800",
    lima: "border-esacom-lime/30 bg-esacom-lime-light text-esacom-ink",
    neutro: "border-gray-200 bg-white text-gray-900",
  };
  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${tonos[tono] || tonos.neutro}`}>
      <p className="text-[10px] font-bold uppercase tracking-wide opacity-70">{titulo}</p>
      <p className="mt-1 text-2xl font-extrabold tracking-tight">{valor}</p>
      <p className="mt-1 text-[11px] leading-snug opacity-75">{detalle}</p>
    </div>
  );
}

function CalidadEquipo({ corte, ultimaCarga }) {
  if (!corte) {
    return <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">Aún no existe una medición de Calidad activa para el equipo.</div>;
  }
  const kpi = Number(corte.pct_cumplimiento || 0);
  const meta = Number(corte.meta_pct || 0);
  const cumple = meta > 0 && kpi >= meta;
  const avance = meta > 0 ? Math.min((kpi / meta) * 100, 100) : Math.min(kpi, 100);
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-bold uppercase tracking-wide text-blue-700">Calidad del equipo · {nombreMes(corte.mes_ano)}</p>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[9px] font-bold text-blue-700 ring-1 ring-blue-100">EN CURSO</span>
          </div>
          <p className="mt-1 text-[11px] text-gray-500">Último avance Claro del período actualmente medido.</p>
        </div>
        <div className="text-left sm:text-right">
          <p className={`text-4xl font-extrabold tracking-tight ${cumple ? "text-green-700" : "text-esacom-red"}`}>{kpi.toFixed(2)}%</p>
          <p className="text-[11px] font-medium text-gray-600">Meta ESACOM {meta.toFixed(0)}%</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className={`rounded-xl p-3 ${cumple ? "bg-green-50" : "bg-red-50"}`}><p className="text-[10px] uppercase text-gray-400">Estado</p><p className={`mt-1 text-base font-extrabold ${cumple ? "text-green-800" : "text-red-800"}`}>{cumple ? "✓ Cumple" : "Aún no cumple"}</p></div>
        <div className="rounded-xl bg-gray-50 p-3"><p className="text-[10px] uppercase text-gray-400">Para llegar a meta</p><p className="mt-1 text-base font-extrabold text-gray-900">{corte.faltan_para_meta || 0} RGU</p></div>
        <div className="rounded-xl bg-green-50 p-3"><p className="text-[10px] uppercase text-green-700">Pago</p><p className="mt-1 text-base font-extrabold text-green-800">{corte.pagadas || 0} RGU</p></div>
        <div className="rounded-xl bg-blue-50 p-3"><p className="text-[10px] uppercase text-blue-700">Pendiente</p><p className="mt-1 text-base font-extrabold text-blue-800">{corte.pendientes || 0} RGU</p></div>
      </div>

      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-[10px] text-gray-500"><span>Avance hacia la meta</span><span>{kpi.toFixed(2)}% / {meta.toFixed(0)}%</span></div>
        <div className="h-2 overflow-hidden rounded-full bg-gray-100"><div className={`h-full ${cumple ? "bg-esacom-green" : "bg-esacom-red"}`} style={{ width: `${avance}%` }} /></div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <div className="rounded-lg bg-red-50 p-2"><span className="text-red-700">Vencido +8</span><strong className="float-right">{corte.gestion?.vencido_mas_8 || 0}</strong></div>
        <div className="rounded-lg bg-orange-50 p-2"><span className="text-orange-700">Vencido 0-8</span><strong className="float-right">{corte.gestion?.vencido_0_8 || 0}</strong></div>
        <div className="rounded-lg bg-yellow-50 p-2"><span className="text-yellow-700">Vence 0-7</span><strong className="float-right">{corte.gestion?.gestionar_0_7 || 0}</strong></div>
        <div className="rounded-lg bg-blue-50 p-2"><span className="text-blue-700">Vence +8</span><strong className="float-right">{corte.gestion?.gestionar_8_mas || 0}</strong></div>
      </div>

      <div className="mt-4 flex flex-col gap-1 border-t border-gray-100 pt-3 text-[10px] text-gray-400 sm:flex-row sm:items-center sm:justify-between">
        <span>Último reporte Claro: {ultimaCarga ? `${ultimaCarga.dia_reporte || "OTRO"} · corte ${ultimaCarga.fecha_corte || "—"}` : "Sin reporte"}</span>
        {corte.valor_informado_claro !== null && corte.valor_informado_claro !== undefined && <span>Referencia Claro: <strong className="text-blue-700">{Number(corte.valor_informado_claro).toFixed(2)}%</strong></span>}
      </div>
    </div>
  );
}

export default function PortalSupervisor() {
  const [resumen, setResumen] = useState(null);
  const [ventas, setVentas] = useState(null);
  const [kpiEquipo, setKpiEquipo] = useState(null);
  const [ultimaCarga, setUltimaCarga] = useState(null);
  const [kpiEjecutivos, setKpiEjecutivos] = useState([]);
  const [honorariosEquipo, setHonorariosEquipo] = useState([]);
  const [snapshotEjecutivos, setSnapshotEjecutivos] = useState(null);
  const [estado, setEstado] = useState("");
  const [perfilKpi, setPerfilKpi] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [busquedaEjecutivo, setBusquedaEjecutivo] = useState("");
  const [error, setError] = useState("");
  const [ejecutivoFiltro, setEjecutivoFiltro] = useState("");
  const [ventaDetalle, setVentaDetalle] = useState(null);
  const [actualizando, setActualizando] = useState(false);
  const [refrescadoEn, setRefrescadoEn] = useState(null);
  const [periodoCartera, setPeriodoCartera] = useState("MES_ACTUAL");

  const cargarPrincipal = useCallback(async ({ silencioso = false, incluirVentas = false } = {}) => {
    if (!silencioso) setActualizando(true);
    try {
      const peticiones = [fetchResumenEquipo(), fetchDashboardKpiCompleto(), fetchKpiPorEjecutivoCompleto()];
      if (incluirVentas) {
        const params = { page_size: 1000 };
        if (estado) params.estado_instalacion = estado;
        if (periodoCartera === "MES_ACTUAL" && resumen?.mes_actual) params.camada = resumen.mes_actual;
        peticiones.push(fetchVentas(params));
      }
      const [r, kpiData, ejecutivosData, ventasData] = await Promise.all(peticiones);
      setResumen(r);
      setKpiEquipo(kpiData.cortes || []);
      setUltimaCarga(kpiData.ultima_carga || null);
      setKpiEjecutivos(ejecutivosData.ejecutivos || []);
      setHonorariosEquipo(ejecutivosData.honorarios || []);
      setSnapshotEjecutivos(ejecutivosData.snapshot || null);
      if (incluirVentas) setVentas(ventasData || []);
      setRefrescadoEn(new Date());
      setError("");
    } catch {
      if (!silencioso) setError("No se pudo actualizar el resumen del equipo.");
    } finally {
      if (!silencioso) setActualizando(false);
    }
  }, [estado, periodoCartera, resumen?.mes_actual]);

  useEffect(() => {
    cargarPrincipal({ incluirVentas: true });
    const timer = window.setInterval(() => cargarPrincipal({ silencioso: true, incluirVentas: true }), 60_000);
    const onFocus = () => cargarPrincipal({ silencioso: true, incluirVentas: true });
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [cargarPrincipal]);

  useEffect(() => {
    const params = { page_size: 1000 };
    if (estado) params.estado_instalacion = estado;
    if (periodoCartera === "MES_ACTUAL" && resumen?.mes_actual) params.camada = resumen.mes_actual;
    fetchVentas(params).then((data) => setVentas(data || [])).catch(() => setError("No se pudo cargar la cartera del equipo."));
  }, [estado, periodoCartera, resumen?.mes_actual]);

  const calidadActual = (kpiEquipo || [])[0] || null;
  const mesActual = resumen?.mes_actual || "";
  const prodEquipo = resumen?.produccion_equipo_mes || null;
  const prodPropia = resumen?.produccion_supervisor_mes || null;
  const actividadEquipo = resumen?.actividad_equipo_mes || null;

  const ranking = useMemo(() => {
    const q = busquedaEjecutivo.trim().toLowerCase();
    return [...(kpiEjecutivos || [])]
      .filter((fila) => {
        if (!q) return true;
        const e = fila.ejecutivo || {};
        return `${e.nombre || ""} ${e.rut || ""} ${e.equipo || ""}`.toLowerCase().includes(q);
      })
      .sort((a, b) => Number(corteActual(a)?.pct_cumplimiento || 0) - Number(corteActual(b)?.pct_cumplimiento || 0));
  }, [kpiEjecutivos, busquedaEjecutivo]);

  const honorariosFiltrados = useMemo(() => {
    const q = busquedaEjecutivo.trim().toLowerCase();
    return [...(honorariosEquipo || [])].filter((fila) => {
      if (!q) return true;
      const e = fila.ejecutivo || {};
      return `${e.nombre || ""} ${e.rut || ""} ${e.equipo || ""}`.toLowerCase().includes(q);
    });
  }, [honorariosEquipo, busquedaEjecutivo]);

  const ejecutivoSeleccionado = useMemo(
    () => (kpiEjecutivos || []).find((x) => String(x.ejecutivo?.id) === String(ejecutivoFiltro))
      || (honorariosEquipo || []).find((x) => String(x.ejecutivo?.id) === String(ejecutivoFiltro))
      || null,
    [kpiEjecutivos, honorariosEquipo, ejecutivoFiltro],
  );

  const ventasFiltradas = useMemo(() => (ventas || []).filter((v) => {
    const ownerId = v.ejecutivo?.id;
    if (ejecutivoFiltro && String(ownerId || "") !== String(ejecutivoFiltro)) return false;
    if (perfilKpi && (v.ejecutivo?.tipo_kpi || "REGULAR") !== perfilKpi) return false;
    if (!busqueda.trim()) return true;
    const q = busqueda.toLowerCase();
    return (v.rut_cliente || "").toLowerCase().includes(q)
      || (v.n_pedido || "").toLowerCase().includes(q)
      || (v.nombre_cliente || "").toLowerCase().includes(q)
      || (v.ejecutivo?.nombre || "").toLowerCase().includes(q);
  }), [ventas, ejecutivoFiltro, perfilKpi, busqueda]);

  const propiaDisponible = Boolean(prodPropia?.disponible);

  return (
    <Layout titulo="Dashboard Supervisor" items={[
      { label: "Mi Equipo", to: "/supervisor" },
      { label: "Accionables", to: "/accionables" },
    ]}>
      {error && <p className="mb-4 rounded-lg bg-esacom-red-light px-4 py-3 text-sm text-esacom-red">{error}</p>}

      <section className="mb-6 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-extrabold text-gray-900">Resumen del equipo</h2>
            <p className="mt-1 text-xs text-gray-500"><strong>{nombreMes(mesActual)}</strong> muestra ventas y RGU actuales de ESACOM. Calidad se actualiza con el período que Claro está midiendo.</p>
            <p className="mt-1 text-[10px] text-gray-400">Última carga ESACOM: {fechaHora(resumen?.ultima_carga_esacom || resumen?.estado_datos?.esacom?.actualizado_en)} · Pantalla consultada: {refrescadoEn ? fechaHora(refrescadoEn) : "—"}</p>
          </div>
          <button type="button" onClick={() => cargarPrincipal({ incluirVentas: true })} disabled={actualizando} className="min-h-11 rounded-xl bg-gray-900 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">
            {actualizando ? "Actualizando…" : "↻ Actualizar"}
          </button>
        </div>
      </section>

      <section className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">Mi equipo · {nombreMes(mesActual)}</h2>
          <p className="text-xs text-gray-500">Producción actual de los ejecutivos asignados. ESACOM es la fuente oficial de ventas, RGU y cantidades.</p>
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <TarjetaResumen titulo="RGU Fijo vendidos" valor={`${prodEquipo?.rgu_fijo_vendidos || 0} RGU`} detalle={`${prodEquipo?.ventas_fijo || 0} ventas · ${prodEquipo?.rgu_fijo_gestionables || 0} gestionables · ${prodEquipo?.rgu_fijo_anulados || 0} anulados`} tono="verde" />
          <TarjetaResumen titulo="Ventas Móvil" valor={`${prodEquipo?.kpi_movil_portadas || 0} portadas`} detalle={`Principal ${prodEquipo?.movil?.principal || 0} · Adicional ${prodEquipo?.movil?.adicional || 0}`} tono="lima" />
          <TarjetaResumen titulo="Actividad del equipo" valor={`${actividadEquipo?.total || 0} ventas`} detalle={`${actividadEquipo?.instaladas || 0} instaladas · ${actividadEquipo?.pendiente_instalacion || 0} pend. instalación`} tono="azul" />
          <TarjetaResumen titulo="Ejecutivos asignados" valor={resumen?.ejecutivos_asignados ?? 0} detalle={`${resumen?.ejecutivos_regulares ?? 0} Regular · ${resumen?.ejecutivos_honorarios ?? 0} Honorarios`} />
        </div>
      </section>

      <section className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">Visual del equipo</h2>
          <p className="text-xs text-gray-500">Gráficos rápidos para detectar estado operativo y prioridades de Calidad sin recorrer toda la tabla.</p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <EstadoVentasDonut actividad={actividadEquipo} titulo={`Estado de ventas · ${nombreMes(mesActual)}`} />
          <UrgenciaBarChart
            titulo={`Prioridad Calidad · ${calidadActual ? nombreMes(calidadActual.mes_ano) : "Sin medición"}`}
            subtitulo="RGU del equipo según urgencia de vencimiento del período en curso."
            items={[
              { name: "Vencido +8", value: calidadActual?.gestion?.vencido_mas_8 },
              { name: "Vencido 0-8", value: calidadActual?.gestion?.vencido_0_8 },
              { name: "Vence 0-7", value: calidadActual?.gestion?.gestionar_0_7 },
              { name: "Vence +8", value: calidadActual?.gestion?.gestionar_8_mas },
            ]}
          />
        </div>
      </section>

      <section className="mb-7 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-base font-extrabold text-gray-900">Mi producción · {nombreMes(mesActual)}</h2>
            <p className="text-xs text-gray-500">Tus ventas propias como Supervisor se muestran separadas de las ventas de tu equipo.</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-[10px] font-bold ${propiaDisponible ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>{propiaDisponible ? "CON VENTAS ACTUALES" : "SIN VENTAS ESTE MES"}</span>
        </div>
        {propiaDisponible ? (
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <TarjetaResumen titulo="Mis RGU Fijo" valor={`${prodPropia?.rgu_fijo_vendidos || 0} RGU`} detalle={`${prodPropia?.ventas_fijo || 0} ventas · ${prodPropia?.rgu_fijo_gestionables || 0} gestionables`} tono="verde" />
            <TarjetaResumen titulo="Mis portadas Móvil" valor={`${prodPropia?.kpi_movil_portadas || 0}`} detalle={`Principal ${prodPropia?.movil?.principal || 0} · Adicional ${prodPropia?.movil?.adicional || 0}`} tono="lima" />
            <TarjetaResumen titulo="Completados Fijo" valor={`${prodPropia?.rgu_fijo_completados || 0} RGU`} detalle={`${prodPropia?.rgu_fijo_pendiente_instalacion || 0} RGU pendientes de instalación`} tono="azul" />
            <TarjetaResumen titulo="Anulados Fijo" valor={`${prodPropia?.rgu_fijo_anulados || 0} RGU`} detalle="Se conservan como venta ESACOM, pero no como gestionables." />
          </div>
        ) : <div className="mt-4 rounded-xl border border-dashed border-gray-300 bg-gray-50 p-5 text-sm text-gray-500">No tienes producción propia registrada en ESACOM durante {nombreMes(mesActual)}. Tu panel de equipo sigue disponible normalmente.</div>}
      </section>

      <section className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">Calidad del equipo</h2>
          <p className="text-xs text-gray-500">Solo se muestra el mes actualmente medido por Claro. Los meses anteriores quedan finalizados o cerrados en histórico.</p>
        </div>
        <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
          <CalidadEquipo corte={calidadActual} ultimaCarga={ultimaCarga} />
          <TendenciaKpiChart corte={calidadActual} />
        </div>
      </section>

      <section className="mb-7">
        <RankingKpiBarChart filas={ranking} obtenerCorte={corteActual} limite={8} />
      </section>

      <section className="mb-7 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-gray-100 p-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Seguimiento de ejecutivos · Calidad actual</h2>
            <p className="mt-1 text-xs text-gray-400">{resumen?.ejecutivos_regulares ?? 0} ejecutivos Regular asignados. Honorarios se mantiene separado.</p>
          </div>
          <input value={busquedaEjecutivo} onChange={(e) => setBusquedaEjecutivo(e.target.value)} placeholder="Buscar ejecutivo por nombre o RUT..." className="min-h-11 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-esacom-red/20 md:w-80" />
        </div>

        <div className="divide-y divide-gray-100 md:hidden">
          {ranking.map((fila) => {
            const e = fila.ejecutivo;
            const c = corteActual(fila);
            const cumple = c && Number(c.pct_cumplimiento || 0) >= Number(c.meta_pct || 0);
            return <div key={`mobile-${e.id}`} className="p-4">
              <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-gray-900">{e.nombre}</p><p className="text-xs text-gray-400">{e.rut}</p></div><div className="text-right"><p className={`text-xl font-bold ${claseKpi(c)}`}>{c ? `${Number(c.pct_cumplimiento || 0).toFixed(2)}%` : "—"}</p><p className="text-[10px] text-gray-400">Meta {c ? `${Number(c.meta_pct || 0).toFixed(0)}%` : "—"}</p></div></div>
              <div className="mt-3 grid grid-cols-4 gap-2 text-center text-[10px]"><div className="rounded-lg bg-green-50 p-2"><strong className="block text-sm text-green-800">{c?.pagadas || 0}</strong>Pago</div><div className="rounded-lg bg-blue-50 p-2"><strong className="block text-sm text-blue-800">{c?.pendientes || 0}</strong>Pend.</div><div className="rounded-lg bg-red-50 p-2"><strong className="block text-sm text-red-800">{c?.no_pago || 0}</strong>No pago</div><div className="rounded-lg bg-gray-50 p-2"><strong className="block text-sm text-gray-900">{c?.faltan_para_meta || 0}</strong>Q meta</div></div>
              <div className="mt-3 flex items-center justify-between"><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${cumple ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{cumple ? "Cumple" : "Aún no cumple"}</span><button onClick={() => setEjecutivoFiltro(String(e.id))} className="min-h-10 rounded-xl bg-esacom-red-light px-3 text-xs font-semibold text-esacom-red">Ver cartera</button></div>
            </div>;
          })}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1050px] text-xs">
            <thead><tr className="bg-gray-50 text-gray-500"><th className="px-4 py-3 text-left">Ejecutivo</th><th className="px-3 py-3 text-center">KPI actual</th><th className="px-3 py-3 text-center">Meta</th><th className="px-3 py-3 text-center">Estado</th><th className="px-3 py-3 text-right">Pago</th><th className="px-3 py-3 text-right">Pendiente</th><th className="px-3 py-3 text-right">No pago</th><th className="px-3 py-3 text-right">Q para meta</th><th className="px-4 py-3"></th></tr></thead>
            <tbody>{ranking.map((fila) => {
              const e = fila.ejecutivo;
              const c = corteActual(fila);
              const cumple = c && Number(c.pct_cumplimiento || 0) >= Number(c.meta_pct || 0);
              return <tr key={e.id} className="border-t border-gray-100 hover:bg-gray-50/60">
                <td className="px-4 py-3"><p className="font-medium text-gray-800">{e.nombre}</p><p className="text-[10px] text-gray-400">{e.rut} · {e.equipo || "Sin equipo"}</p></td>
                <td className={`px-3 py-3 text-center font-bold ${claseKpi(c)}`}>{c ? `${Number(c.pct_cumplimiento || 0).toFixed(2)}%` : "—"}</td>
                <td className="px-3 py-3 text-center">{c ? `${Number(c.meta_pct || 0).toFixed(0)}%` : "—"}</td>
                <td className="px-3 py-3 text-center"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${cumple ? "bg-green-50 text-green-700" : c ? "bg-red-50 text-red-700" : "bg-gray-100 text-gray-400"}`}>{c ? (cumple ? "Cumple" : "No cumple") : "Sin datos"}</span></td>
                <td className="px-3 py-3 text-right font-semibold text-green-700">{c?.pagadas || 0}</td><td className="px-3 py-3 text-right font-semibold text-blue-700">{c?.pendientes || 0}</td><td className="px-3 py-3 text-right font-semibold text-red-700">{c?.no_pago || 0}</td><td className="px-3 py-3 text-right font-semibold text-esacom-red">{c?.faltan_para_meta || 0} RGU</td>
                <td className="px-4 py-3 text-right"><button onClick={() => setEjecutivoFiltro(String(e.id))} className="text-[11px] font-semibold text-esacom-red hover:underline">Ver cartera</button></td>
              </tr>;
            })}</tbody>
          </table>
        </div>
        {ranking.length === 0 && <p className="p-6 text-center text-sm text-gray-400">No hay KPI actual atribuido a ejecutivos del equipo.</p>}
      </section>

      <section className="mb-7 overflow-hidden rounded-2xl border border-amber-200 bg-white shadow-sm">
        <div className="flex flex-col gap-2 border-b border-amber-100 bg-amber-50/50 p-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Seguimiento Honorarios · Calidad actual</h2>
            <p className="mt-1 text-xs text-amber-800">Se muestra el KPI real de pago y la producción ESACOM del mes. Honorarios no participa en la meta, promedio ni ranking Regular.</p>
          </div>
          <span className="text-[11px] font-semibold text-amber-700">Meta Honorarios: pendiente de definición</span>
        </div>
        <div className="divide-y divide-gray-100 md:hidden">
          {honorariosFiltrados.map((fila) => {
            const e = fila.ejecutivo || {};
            const c = fila.calidad_actual;
            const p = fila.produccion_mes_actual || {};
            return <div key={`hon-mobile-${e.id}`} className="p-4">
              <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-gray-900">{e.nombre}</p><p className="text-xs text-gray-400">{e.rut}</p></div><div className="text-right"><p className="text-xl font-bold text-blue-700">{c?.tiene_datos ? `${Number(c.pct_cumplimiento || 0).toFixed(2)}%` : "Sin medición"}</p><p className="text-[10px] text-gray-400">KPI de pago</p></div></div>
              <div className="mt-3 grid grid-cols-4 gap-2 text-center text-[10px]"><div className="rounded-lg bg-green-50 p-2"><strong className="block text-sm text-green-800">{p?.ventas_fijo || 0}</strong>Ventas mes</div><div className="rounded-lg bg-gray-50 p-2"><strong className="block text-sm text-gray-900">{p?.rgu_fijo_vendidos || 0}</strong>RGU mes</div><div className="rounded-lg bg-green-50 p-2"><strong className="block text-sm text-green-800">{c?.pagadas || 0}</strong>Pago</div><div className="rounded-lg bg-gray-50 p-2"><strong className="block text-sm text-gray-900">{c?.total || 0}</strong>Total KPI</div></div>
              <div className="mt-3 flex items-center justify-between"><span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">Sin meta aplicada</span><button onClick={() => setEjecutivoFiltro(String(e.id))} className="min-h-10 rounded-xl bg-amber-50 px-3 text-xs font-semibold text-amber-800">Ver cartera</button></div>
            </div>;
          })}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1050px] text-xs">
            <thead><tr className="bg-gray-50 text-gray-500"><th className="px-4 py-3 text-left">Ejecutivo Honorarios</th><th className="px-3 py-3 text-center">Ventas {nombreMes(mesActual)}</th><th className="px-3 py-3 text-center">RGU {nombreMes(mesActual)}</th><th className="px-3 py-3 text-center">KPI pago actual</th><th className="px-3 py-3 text-right">Pago</th><th className="px-3 py-3 text-right">Pendiente</th><th className="px-3 py-3 text-right">No pago</th><th className="px-3 py-3 text-right">Fuera plazo</th><th className="px-3 py-3 text-right">Total RGU KPI</th><th className="px-4 py-3"></th></tr></thead>
            <tbody>{honorariosFiltrados.map((fila) => {
              const e = fila.ejecutivo || {};
              const c = fila.calidad_actual;
              const p = fila.produccion_mes_actual || {};
              return <tr key={`hon-${e.id}`} className="border-t border-gray-100 hover:bg-amber-50/30">
                <td className="px-4 py-3"><p className="font-medium text-gray-800">{e.nombre}</p><p className="text-[10px] text-gray-400">{e.rut} · Honorarios</p></td>
                <td className="px-3 py-3 text-center font-semibold text-gray-800">{p?.ventas_fijo || 0}</td>
                <td className="px-3 py-3 text-center font-semibold text-gray-800">{p?.rgu_fijo_vendidos || 0}</td>
                <td className="px-3 py-3 text-center font-bold text-blue-700">{c?.tiene_datos ? `${Number(c.pct_cumplimiento || 0).toFixed(2)}%` : "—"}</td>
                <td className="px-3 py-3 text-right font-semibold text-green-700">{c?.pagadas || 0}</td><td className="px-3 py-3 text-right font-semibold text-blue-700">{c?.pendientes || 0}</td><td className="px-3 py-3 text-right font-semibold text-red-700">{c?.no_pago || 0}</td><td className="px-3 py-3 text-right font-semibold text-orange-700">{c?.fuera_plazo || 0}</td><td className="px-3 py-3 text-right font-semibold text-gray-800">{c?.total || 0}</td>
                <td className="px-4 py-3 text-right"><button onClick={() => setEjecutivoFiltro(String(e.id))} className="text-[11px] font-semibold text-amber-700 hover:underline">Ver cartera</button></td>
              </tr>;
            })}</tbody>
          </table>
        </div>
        {honorariosFiltrados.length === 0 && <p className="p-6 text-center text-sm text-gray-400">No hay ejecutivos Honorarios activos asignados o no coinciden con la búsqueda.</p>}
      </section>

      <section>
        <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div><h2 className="text-base font-extrabold text-gray-900">Cartera del equipo</h2><p className="text-xs text-gray-500">Por defecto muestra {nombreMes(mesActual)}. Fuente oficial ESACOM.</p></div>
          {snapshotEjecutivos && <span className="text-[11px] text-gray-400">Corte Calidad {snapshotEjecutivos.fecha_corte || "—"}</span>}
        </div>
        {ejecutivoFiltro && <div className="mb-3 flex flex-col gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-800 sm:flex-row sm:items-center sm:justify-between"><span>Ejecutivo: <strong>{ejecutivoSeleccionado?.ejecutivo?.nombre || "seleccionado"}</strong></span><button onClick={() => setEjecutivoFiltro("")} className="min-h-9 rounded-lg bg-white/70 px-3 font-semibold">Ver todo el equipo</button></div>}
        <div className="mb-4 flex flex-col gap-3 md:flex-row">
          <input type="text" placeholder="Buscar cliente, RUT, pedido o ejecutivo..." value={busqueda} onChange={(e) => setBusqueda(e.target.value)} className="min-h-11 flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-esacom-red/20" />
          <select value={periodoCartera} onChange={(e) => setPeriodoCartera(e.target.value)} className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"><option value="MES_ACTUAL">Mes actual</option><option value="TODAS">Toda la cartera</option></select>
          <select value={perfilKpi} onChange={(e) => setPerfilKpi(e.target.value)} className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"><option value="">Regular + Honorarios</option><option value="REGULAR">Solo Regular</option><option value="HONORARIOS">Solo Honorarios</option></select>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm">{ESTADOS.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}</select>
        </div>

        {ventas === null && <div className="h-64 animate-pulse rounded-xl bg-gray-100" />}
        {ventas && ventasFiltradas.length === 0 && <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-400">No hay clientes que coincidan con los filtros.</div>}
        {ventas && ventasFiltradas.length > 0 && <div className="space-y-2">{ventasFiltradas.map((v) => <button type="button" onClick={() => setVentaDetalle(v.id)} key={v.id} className="w-full rounded-2xl border border-gray-200 bg-white p-4 text-left transition hover:border-gray-300 hover:shadow-sm active:scale-[0.998]"><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-sm font-medium text-gray-900">{v.nombre_cliente || v.rut_cliente}</p><p className="text-xs text-gray-400">{v.rut_cliente} · {v.n_pedido}</p></div><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${ESTADO_BADGE[v.estado_instalacion] || "bg-gray-100 text-gray-500"}`}>{ESTADOS.find((e) => e.value === v.estado_instalacion)?.label || v.estado_instalacion}</span></div><div className="mt-2 flex flex-wrap items-center gap-2"><p className="text-xs font-medium text-blue-600">{v.ejecutivo?.nombre || "Sin ejecutivo"}</p>{v.ejecutivo && <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${v.ejecutivo.tipo_kpi === "HONORARIOS" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-gray-200 bg-gray-50 text-gray-500"}`}>{v.ejecutivo.tipo_kpi === "HONORARIOS" ? "HONORARIOS" : "REGULAR"}</span>}</div><div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"><div><p className="text-gray-400">Producto</p><p>{v.promocion?.nombre || "—"}</p></div><div><p className="text-gray-400">F. venta</p><p>{v.fecha_venta || "—"}</p></div><div><p className="text-gray-400">1ª agenda</p><p>{v.primera_agenda || "—"}</p></div><div><p className="text-gray-400">F. cierre</p><p>{v.fecha_cierre || "—"}</p></div></div></button>)}</div>}
      </section>

      <ClienteDetalleModal ventaId={ventaDetalle} onClose={() => setVentaDetalle(null)} />
    </Layout>
  );
}
