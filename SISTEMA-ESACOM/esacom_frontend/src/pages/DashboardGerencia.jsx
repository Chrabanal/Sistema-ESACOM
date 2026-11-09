import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { ADMIN_URL } from "../api/client";
import {
  buscarUsuarioGerencia,
  fetchDashboardGerencia,
  fetchUsuarioGerenciaDetalle,
} from "../api/dashboard";

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function nombreMes(valor) {
  if (!valor || !String(valor).includes("-")) return valor || "—";
  const [anio, mes] = String(valor).split("-");
  return `${MESES[Number(mes) - 1]} ${anio}`;
}

function numero(valor) {
  return Number(valor || 0).toLocaleString("es-CL");
}

function porcentaje(valor) {
  return valor == null ? "—" : `${Number(valor).toFixed(2)}%`;
}

function fechaHora(valor) {
  if (!valor) return "Sin sincronización registrada";
  const d = new Date(valor);
  if (Number.isNaN(d.getTime())) return valor;
  return d.toLocaleString("es-CL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fechaCorta(valor) {
  if (!valor) return "—";
  const partes = String(valor).split("-");
  if (partes.length === 3) return `${partes[2]}/${partes[1]}/${partes[0]}`;
  return valor;
}

function TarjetaOperacion({ label, value, detail, tone = "dark" }) {
  const tones = {
    green: "text-green-700",
    blue: "text-blue-700",
    orange: "text-orange-600",
    red: "text-red-700",
    dark: "text-gray-900",
  };
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-black sm:text-3xl ${tones[tone] || tones.dark}`}>{value}</p>
      {detail && <p className="mt-1 text-[11px] text-gray-400">{detail}</p>}
    </div>
  );
}

function TarjetaCalidad({ corte, referenciaClaro }) {
  if (!corte) return null;
  const meta = Number(corte.meta_pct || 0);
  const kpi = Number(corte.pct_cumplimiento || 0);
  const cumple = meta > 0 && kpi >= meta;
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-bold text-gray-900">{corte.boleta} · {nombreMes(corte.mes_ano)}</p>
            <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-700">MEDICIÓN VIGENTE</span>
          </div>
          <p className={`mt-2 text-3xl font-black ${cumple ? "text-green-700" : "text-red-700"}`}>{porcentaje(kpi)}</p>
        </div>
        <div className="text-right text-[11px] text-gray-500">
          <p>Meta ESACOM <strong className="text-gray-900">{porcentaje(meta)}</strong></p>
          <p className="mt-1">Referencia Claro <strong className="text-blue-700">{porcentaje(referenciaClaro)}</strong></p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-gray-100 pt-4 sm:grid-cols-5">
        {[
          ["Pago", corte.pagadas, "text-green-700"],
          ["Pendiente", corte.pendientes, "text-blue-700"],
          ["Q para meta", corte.faltan_para_meta, "text-gray-900"],
          ["No pago", corte.no_pago, "text-red-700"],
          ["Fuera plazo", corte.fuera_plazo, "text-orange-600"],
        ].map(([label, value, color]) => (
          <div key={label}>
            <p className="text-[10px] uppercase text-gray-400">{label}</p>
            <p className={`mt-1 text-lg font-bold ${color}`}>{numero(value)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardGerencia() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [resultados, setResultados] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [usuarioSeleccionado, setUsuarioSeleccionado] = useState(null);
  const [detalleUsuario, setDetalleUsuario] = useState(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);

  const cargar = () => {
    setError("");
    fetchDashboardGerencia()
      .then(setData)
      .catch(() => setError("No se pudo cargar el dashboard de Gerencia."));
  };

  useEffect(() => { cargar(); }, []);

  useEffect(() => {
    const q = busqueda.trim();
    if (usuarioSeleccionado && q === usuarioSeleccionado.nombre) {
      setResultados([]);
      setBuscando(false);
      return undefined;
    }
    if (q.length < 2) {
      setResultados([]);
      setBuscando(false);
      return undefined;
    }
    let activo = true;
    const timer = setTimeout(async () => {
      setBuscando(true);
      try {
        const items = await buscarUsuarioGerencia(q);
        if (activo) setResultados(items);
      } catch {
        if (activo) setResultados([]);
      } finally {
        if (activo) setBuscando(false);
      }
    }, 250);
    return () => {
      activo = false;
      clearTimeout(timer);
    };
  }, [busqueda, usuarioSeleccionado]);

  async function seleccionarUsuario(usuario) {
    setUsuarioSeleccionado(usuario);
    setBusqueda(usuario.nombre);
    setResultados([]);
    setCargandoDetalle(true);
    setDetalleUsuario(null);
    try {
      const detalle = await fetchUsuarioGerenciaDetalle(usuario.id);
      setDetalleUsuario(detalle);
    } catch {
      setDetalleUsuario(null);
    } finally {
      setCargandoDetalle(false);
    }
  }

  const globalPorBoleta = useMemo(() => {
    const mapa = {};
    for (const item of data?.global || []) mapa[item.boleta] = item;
    return mapa;
  }, [data]);

  const filasHistorico = useMemo(() => {
    if (!detalleUsuario) return [];
    const filas = [];
    for (const actual of detalleUsuario.calidad_abierta || (detalleUsuario.calidad_actual ? [detalleUsuario.calidad_actual] : [])) {
      if (actual?.tiene_datos) filas.push({ ...actual, es_actual: true });
    }
    for (const item of detalleUsuario.historico_kpi || []) filas.push({ ...item, es_actual: false });
    return filas;
  }, [detalleUsuario]);

  const operacion = data?.operacion || {};
  const mesActual = operacion.mes_actual || "";
  const produccionMes = operacion.produccion_mes || {};
  const controlOperativo = operacion.control_operativo || {};

  return (
    <Layout
      titulo="Dashboard Gerencia"
      items={[
        { label: "Dashboard", to: "/dashboard" },
        { label: "Ejecutivos", to: "/ejecutivos" },
        { label: "Cierres KPI", to: "/cierres-kpi" },
        { label: "Accionables", to: "/accionables" },
        { label: "Cobranza", to: "/cobranza" },
        { label: "Apelaciones", to: "/apelaciones" },
        { label: "Base de Datos", to: "/base-datos" },
        { label: "Histórico", to: "/historico" },
        { label: "Análisis", to: "/analisis" },
        { label: "Cargar Datos", to: "/cargar-datos" },
        { label: "Auditoría KPI", to: "/auditoria-kpi" },
        { label: "Permisos", to: "/permisos" },
        { label: "Admin", href: ADMIN_URL },
      ]}
    >
      {error && <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {!error && !data && <div className="h-72 animate-pulse rounded-2xl bg-gray-100" />}

      {data && (
        <div className="space-y-6 pb-8">
          <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-full border border-green-200 bg-green-50 text-xl text-green-700">↻</div>
                <div>
                  <p className="text-sm font-bold text-gray-900">Datos ESACOM actualizados</p>
                  <p className="text-sm text-gray-500">{fechaHora(operacion.ultima_sync_esacom)}</p>
                  <p className="mt-0.5 text-[11px] text-gray-400">Fuente operacional vigente ESACOM</p>
                </div>
              </div>
              <button onClick={cargar} className="min-h-11 rounded-xl bg-gray-900 px-5 text-sm font-semibold text-white hover:bg-black">
                ↻ Actualizar
              </button>
            </div>
          </section>

          <section>
            <div className="mb-3 border-l-4 border-lime-500 pl-3">
              <h2 className="text-lg font-bold text-gray-900">Producción del mes · {nombreMes(mesActual)}</h2>
              <p className="text-xs text-gray-500">Solo ventas del mes calendario. Este bloque no se usa para cuadrar el control diario vigente.</p>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <TarjetaOperacion label="Clientes del mes" value={numero(operacion.clientes)} detail="Clientes únicos del período" />
              <TarjetaOperacion label="RGU Fijo vendidos" value={numero(produccionMes.rgu_fijo_vendidos)} detail={`${numero(produccionMes.ventas_fijo)} ventas del mes`} tone="green" />
              <TarjetaOperacion label="Portadas Móvil del mes" value={numero(produccionMes.movil_portadas)} detail={`Principal ${numero(produccionMes.movil_principal)} · Adicional ${numero(produccionMes.movil_adicional)}`} tone="blue" />
              <TarjetaOperacion label="RGU Fijo gestionables del mes" value={numero(produccionMes.rgu_fijo_gestionables)} detail={`Anulados ${numero(produccionMes.rgu_fijo_anulados)}`} />
            </div>
          </section>

          <section>
            <div className="mb-3 border-l-4 border-lime-500 pl-3">
              <h2 className="text-lg font-bold text-gray-900">Control operativo ESACOM · Hoy</h2>
              <p className="text-xs text-gray-500">Fotografía vigente para cuadrar con el control diario de Gerencia. Fijo se expresa en RGU y Móvil en líneas efectivas; puede incluir ventas de meses anteriores que siguen activas en la base.</p>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <TarjetaOperacion label="Fijo completado" value={numero(controlOperativo.rgu_completadas)} detail="RGU base vigente" tone="green" />
              <TarjetaOperacion label="Fijo pend. instalación" value={numero(controlOperativo.rgu_pendiente_instalacion)} detail="RGU base vigente" tone="orange" />
              <TarjetaOperacion label="Fijo total en control" value={numero(controlOperativo.rgu_total_control)} detail="Completado + pend. instalación" />
              <TarjetaOperacion label="Portadas móviles vigentes" value={numero(controlOperativo.movil_portadas)} detail={`Principal ${numero(controlOperativo.movil_principal)} · Adicional ${numero(controlOperativo.movil_adicional)}`} tone="blue" />
              <TarjetaOperacion label="Móvil por activar" value={numero(controlOperativo.movil_pendiente_activacion)} detail="Líneas vigentes no efectivas" />
              <TarjetaOperacion label="Pend. comercial Fijo" value={numero(controlOperativo.rgu_pendiente_comercial)} detail="RGU fuera del total de instalación" tone="blue" />
              <TarjetaOperacion label="Ejecutivos activos" value={numero(operacion.ejecutivos_activos)} detail={`${numero(operacion.ejecutivos_regulares_activos)} Regular · ${numero(operacion.ejecutivos_honorarios_activos)} Honorarios`} />
              <TarjetaOperacion label="Supervisores activos" value={numero(operacion.supervisores_activos)} />
            </div>

            {Object.keys(controlOperativo.movil_por_supervisor || {}).length > 0 && (
              <div className="mt-3 rounded-2xl border border-blue-100 bg-blue-50/40 p-4 shadow-sm">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-bold text-gray-900">Portadas móviles vigentes por supervisor</p>
                    <p className="text-xs text-gray-500">Mismo criterio del control diario: línea vigente + efectiva. La producción propia de un Supervisor se agrupa por el supervisor informado por ESACOM.</p>
                  </div>
                  <p className="text-xs font-semibold text-blue-700">Total {numero(controlOperativo.movil_portadas)} portadas</p>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                  {Object.entries(controlOperativo.movil_por_supervisor).map(([nombre, datos]) => (
                    <div key={nombre} className="rounded-xl bg-white px-3 py-2">
                      <p className="truncate text-[11px] text-gray-500" title={nombre}>{nombre}</p>
                      <p className="mt-1 text-lg font-black text-blue-800">{numero(datos?.total)}</p>
                      <p className="text-[10px] text-gray-400">P {numero(datos?.principal)} · A {numero(datos?.adicional)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(controlOperativo.fijo_por_supervisor || {}).length > 0 && (
              <div className="mt-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-bold text-gray-900">Fijo vigente por supervisor</p>
                    <p className="text-xs text-gray-400">Mismo universo del control diario: completadas + pendiente instalación, expresado en RGU.</p>
                  </div>
                  <p className="text-xs text-gray-400">Total control {numero(controlOperativo.rgu_total_control)} RGU</p>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                  {Object.entries(controlOperativo.fijo_por_supervisor).map(([nombre, datos]) => (
                    <div key={nombre} className="rounded-xl bg-gray-50 px-3 py-2">
                      <p className="truncate text-[11px] text-gray-500" title={nombre}>{nombre}</p>
                      <p className="mt-1 text-lg font-black text-gray-900">{numero(datos?.total_control)}</p>
                      <p className="text-[10px] text-gray-400">C {numero(datos?.completadas)} · P {numero(datos?.pendiente_instalacion)}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {(data.calidad_abierta || []).length > 0 && (
            <section>
              <div className="mb-3 border-l-4 border-blue-500 pl-3">
                <h2 className="text-lg font-bold text-gray-900">Camadas B1 abiertas</h2>
                <p className="text-xs text-gray-500">Todas las camadas Fijo que siguen en AVANCE. Una camada desaparece de esta sección solo cuando existe CIERRE_FIJO oficial.</p>
              </div>
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {(data.calidad_abierta || []).map((corte) => (
                  <TarjetaCalidad key={`abierta-${corte.mes_ano}-${corte.boleta}`} corte={corte} referenciaClaro={corte.valor_informado_claro} />
                ))}
              </div>
            </section>
          )}

          <section>
            <div className="mb-3 border-l-4 border-lime-500 pl-3">
              <h2 className="text-lg font-bold text-gray-900">Focos del último reporte Claro</h2>
              <p className="text-xs text-gray-500">B1/B2/B3 declarados en RESUMEN GESTION RGU. Se mantienen como referencia del correo, pero no ocultan otras camadas presentes en BASE.</p>
            </div>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              {["B1", "B2", "B3"].map((b) => (
                <TarjetaCalidad
                  key={b}
                  corte={globalPorBoleta[b]}
                  referenciaClaro={data.snapshot_actual?.avances_claro?.[b]}
                />
              ))}
            </div>
          </section>

          <section>
            <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div className="border-l-4 border-lime-500 pl-3">
                <h2 className="text-lg font-bold text-gray-900">Consultar KPI por usuario</h2>
                <p className="text-xs text-gray-500">Busca por nombre o RUT para ver Calidad actual, producción del mes e histórico congelado.</p>
              </div>
              <div className="relative w-full lg:w-[440px]">
                <input
                  value={busqueda}
                  onChange={(e) => {
                    setBusqueda(e.target.value);
                    if (usuarioSeleccionado && e.target.value !== usuarioSeleccionado.nombre) {
                      setUsuarioSeleccionado(null);
                      setDetalleUsuario(null);
                    }
                  }}
                  placeholder="Buscar por nombre o RUT..."
                  className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm outline-none focus:border-gray-500"
                />
                {(buscando || resultados.length > 0) && (
                  <div className="absolute z-20 mt-2 max-h-72 w-full overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-xl">
                    {buscando && <p className="px-4 py-3 text-sm text-gray-400">Buscando...</p>}
                    {!buscando && resultados.map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => seleccionarUsuario(u)}
                        className="block w-full border-b border-gray-100 px-4 py-3 text-left last:border-0 hover:bg-gray-50"
                      >
                        <p className="text-sm font-semibold text-gray-900">{u.nombre}</p>
                        <p className="text-xs text-gray-400">{u.rut} · {u.cargo} · {u.tipo_kpi}{!u.is_active ? " · Inactivo" : ""}</p>
                      </button>
                    ))}
                    {!buscando && !resultados.length && <p className="px-4 py-3 text-sm text-gray-400">Sin coincidencias.</p>}
                  </div>
                )}
              </div>
            </div>

            {!usuarioSeleccionado && (
              <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
                Busca y selecciona una persona para abrir su ficha KPI.
              </div>
            )}

            {usuarioSeleccionado && cargandoDetalle && (
              <div className="h-56 animate-pulse rounded-2xl bg-gray-100" />
            )}

            {usuarioSeleccionado && !cargandoDetalle && detalleUsuario && (
              <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
                <div className="flex flex-col gap-3 border-b border-gray-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-base font-bold text-gray-900">{detalleUsuario.usuario.nombre}</p>
                    <p className="text-xs text-gray-400">RUT {detalleUsuario.usuario.rut}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {detalleUsuario.usuario.supervisor_nombre && (
                      <span className="rounded-lg bg-gray-50 px-3 py-2 text-gray-600">Supervisor: <strong>{detalleUsuario.usuario.supervisor_nombre}</strong></span>
                    )}
                    <span className="rounded-lg bg-gray-50 px-3 py-2 text-gray-600">Rol: <strong>{detalleUsuario.usuario.cargo}</strong></span>
                    <span className={`rounded-full px-3 py-2 font-bold ${detalleUsuario.usuario.tipo_kpi === "HONORARIOS" ? "bg-purple-50 text-purple-700" : "bg-green-50 text-green-700"}`}>
                      {detalleUsuario.usuario.tipo_kpi}
                    </span>
                  </div>
                </div>

                <div className="mt-4 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-green-100 bg-green-50/40 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="font-bold text-gray-900">KPI actual · {nombreMes(detalleUsuario.calidad_actual?.mes_ano)}</h3>
                      {detalleUsuario.calidad_actual?.meta_definida !== false && detalleUsuario.calidad_actual?.tiene_datos && (
                        <span className={`rounded-full px-3 py-1 text-xs font-bold ${Number(detalleUsuario.calidad_actual?.pct_cumplimiento || 0) >= Number(detalleUsuario.calidad_actual?.meta_pct || 0) ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
                          {Number(detalleUsuario.calidad_actual?.pct_cumplimiento || 0) >= Number(detalleUsuario.calidad_actual?.meta_pct || 0) ? "Cumple" : "No cumple"}
                        </span>
                      )}
                    </div>
                    {detalleUsuario.calidad_actual?.tiene_datos ? (
                      <>
                        <div className="mt-3 grid gap-4 sm:grid-cols-[180px_1fr]">
                          <div>
                            <p className="text-4xl font-black text-green-700">{porcentaje(detalleUsuario.calidad_actual.pct_cumplimiento)}</p>
                            <p className="mt-1 text-xs text-gray-500">
                              {detalleUsuario.calidad_actual.meta_definida === false
                                ? "Honorarios · sin meta Regular aplicada"
                                : `Meta ESACOM ${porcentaje(detalleUsuario.calidad_actual.meta_pct)}`}
                            </p>
                            <p className="mt-1 text-xs text-gray-500">Referencia Claro {detalleUsuario.calidad_actual.valor_informado_claro == null ? "No informada para esta camada" : porcentaje(detalleUsuario.calidad_actual.valor_informado_claro)}</p>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                            {[
                              ["Pago", detalleUsuario.calidad_actual.pagadas, "text-green-700"],
                              ["Pendiente", detalleUsuario.calidad_actual.pendientes, "text-blue-700"],
                              ["No pago", detalleUsuario.calidad_actual.no_pago, "text-red-700"],
                              ["Fuera plazo", detalleUsuario.calidad_actual.fuera_plazo, "text-orange-600"],
                              ["Q para meta", detalleUsuario.calidad_actual.meta_definida === false ? "—" : detalleUsuario.calidad_actual.faltan_para_meta, "text-gray-900"],
                              ["Corte Claro", fechaCorta(detalleUsuario.calidad_actual.fecha_corte), "text-gray-900"],
                            ].map(([label, value, color]) => (
                              <div key={label} className="rounded-xl bg-white p-3">
                                <p className="text-[10px] uppercase text-gray-400">{label}</p>
                                <p className={`mt-1 font-bold ${color}`}>{value}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    ) : (
                      <p className="mt-3 text-sm text-gray-400">Sin medición KPI vigente para esta persona.</p>
                    )}
                  </div>

                  <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4">
                    <h3 className="font-bold text-gray-900">Producción actual · {nombreMes(detalleUsuario.mes_actual)}</h3>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-xl bg-white p-4">
                        <p className="text-xs font-bold text-gray-700">Fijo</p>
                        <p className="mt-1 text-3xl font-black text-green-700">{numero(detalleUsuario.produccion_mes_actual?.rgu_fijo_vendidos)} <span className="text-sm font-semibold">RGU</span></p>
                        <p className="mt-2 text-xs text-gray-500">{numero(detalleUsuario.produccion_mes_actual?.ventas_fijo)} ventas · {numero(detalleUsuario.produccion_mes_actual?.rgu_fijo_gestionables)} gestionables · {numero(detalleUsuario.produccion_mes_actual?.rgu_fijo_anulados)} RGU anulados</p>
                      </div>
                      <div className="rounded-xl bg-white p-4">
                        <p className="text-xs font-bold text-gray-700">Móvil vigente</p>
                        <p className="mt-1 text-3xl font-black text-blue-700">{numero(detalleUsuario.produccion_mes_actual?.kpi_movil_portadas)} <span className="text-sm font-semibold">portadas</span></p>
                        <p className="mt-2 text-xs text-gray-500">Efectivas vigentes · Principal {numero(detalleUsuario.produccion_mes_actual?.movil?.principal)} · Adicional {numero(detalleUsuario.produccion_mes_actual?.movil?.adicional)}</p>
                      </div>
                    </div>
                    {detalleUsuario.usuario.cargo === "SUPERVISOR" && detalleUsuario.equipo && (
                      <p className="mt-3 text-xs text-gray-500">Equipo vigente: <strong>{detalleUsuario.equipo.total}</strong> ejecutivos · {detalleUsuario.equipo.regular} Regular · {detalleUsuario.equipo.honorarios} Honorarios.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </section>

          {detalleUsuario && filasHistorico.length > 0 && (
            <section>
              <div className="mb-3 border-l-4 border-lime-500 pl-3">
                <h2 className="text-lg font-bold text-gray-900">Histórico KPI Calidad Fijo</h2>
                <p className="text-xs text-gray-500">Las camadas en AVANCE se muestran como En curso; el Histórico queda reservado a CIERRE oficial.</p>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="border-b border-gray-200 bg-gray-50 text-[11px] uppercase text-gray-400">
                    <tr>
                      <th className="px-4 py-3 text-left">Período</th>
                      <th className="px-4 py-3 text-right">KPI</th>
                      <th className="px-4 py-3 text-right">Pago / Total</th>
                      <th className="px-4 py-3 text-right">Meta ESACOM</th>
                      <th className="px-4 py-3 text-right">Referencia Claro</th>
                      <th className="px-4 py-3 text-right">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filasHistorico.map((h, idx) => (
                      <tr key={`${h.mes_ano}-${h.boleta}-${idx}`}>
                        <td className="px-4 py-3 font-medium text-gray-800">{nombreMes(h.mes_ano)}</td>
                        <td className="px-4 py-3 text-right font-bold text-green-700">{porcentaje(h.pct_cumplimiento)}</td>
                        <td className="px-4 py-3 text-right text-gray-700">{numero(h.pagadas)} / {numero(h.total)}</td>
                        <td className="px-4 py-3 text-right text-gray-500">{h.meta_definida === false ? "—" : porcentaje(h.meta_pct)}</td>
                        <td className="px-4 py-3 text-right text-gray-500">{porcentaje(h.valor_informado_claro)}</td>
                        <td className="px-4 py-3 text-right">
                          <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${h.es_actual ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-600"}`}>
                            {h.es_actual ? "En curso" : (h.cierre_oficial ? "Cierre oficial" : "Cierre")}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <p className="text-xs text-gray-400">El dashboard separa operación actual ESACOM, KPI vigente y histórico congelado.</p>
        </div>
      )}
    </Layout>
  );
}
