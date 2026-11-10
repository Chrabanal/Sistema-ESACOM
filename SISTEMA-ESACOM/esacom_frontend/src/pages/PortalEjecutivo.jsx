import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import KpiCard from "../components/KpiCard";
import ClienteDetalleModal from "../components/ClienteDetalleModal";
import TarjetasEstadoComercial from "../components/TarjetasEstadoComercial";
import { MotivosPendienteBarChart, UrgenciaBarChart } from "../components/DashboardCharts";
import VencimientoPrimeraBoletaChart from "../components/VencimientoPrimeraBoletaChart";
import { fetchAccionables, fetchDashboardKpiCompleto } from "../api/dashboard";
import { fetchVentas, registrarGestion, fetchCortesB1Pendientes } from "../api/apelaciones";

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

const ESTADO_BOLETA = {
  PAGADO: {
    label: "Pagada",
    clase: "bg-green-100 text-green-700",
  },
  PENDIENTE: {
    label: "Pendiente",
    clase: "bg-amber-100 text-amber-700",
  },
  NO_PAGO: {
    label: "No pago",
    clase: "bg-red-100 text-red-700",
  },
  FUERA_PLAZO: {
    label: "Pagada fuera de plazo",
    clase: "bg-orange-100 text-orange-700",
  },
  SIN_BOLETA: {
    label: "Sin boleta",
    clase: "bg-gray-100 text-gray-600",
  },
};

function fechaCorta(valor) {
  if (!valor) return "—";
  const partes = String(valor).slice(0, 10).split("-");
  if (partes.length !== 3) return valor;
  return `${partes[2]}/${partes[1]}`;
}

function fechaVencida(valor) {
  if (!valor) return false;
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);

  const fecha = new Date(`${String(valor).slice(0, 10)}T12:00:00`);
  return fecha < hoy;
}

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

function ClienteCard({
  venta,
  onDetalle,
  activoPago = false,
  mesSeleccionado,
  boletaActivaMes,
}) {
  const [enviando, setEnviando] = useState(null);

  const cortesResumen = Array.isArray(venta.cortes_resumen)
    ? venta.cortes_resumen
    : [];

  const corteActual =
    cortesResumen.find(
      (c) =>
        c.mes_ano === mesSeleccionado &&
        (!boletaActivaMes || c.boleta === boletaActivaMes)
    ) || null;

  const estadoBoleta = corteActual
    ? ESTADO_BOLETA[corteActual.estado_pago] || {
        label: corteActual.estado_pago || "Aún sin boleta",
        clase: "bg-gray-100 text-gray-600",
      }
    : null;

  const estadoVisual = {
    INSTALADO: {
      borde: "border-l-green-500",
      fondo: "bg-green-50/30",
    },
    PENDIENTE_INSTALACION: {
      borde: "border-l-orange-500",
      fondo: "bg-orange-50/30",
    },
    PENDIENTE_COMERCIAL: {
      borde: "border-l-yellow-500",
      fondo: "bg-yellow-50/30",
    },
    ANULADO: {
      borde: "border-l-red-500",
      fondo: "bg-red-50/30",
    },
  };

  const visual = estadoVisual[venta.estado_instalacion] || {
    borde: "border-l-gray-300",
    fondo: "bg-white",
  };

  async function handleClick(tipo, href) {
    setEnviando(tipo);

    try {
      await registrarGestion(venta.id, tipo);
    } catch {
      // El contacto no debe bloquearse por una falla de auditoría.
    } finally {
      setEnviando(null);

      if (href) {
        window.open(href, "_blank");
      }
    }
  }

  return (
    <article
      className={`overflow-hidden rounded-2xl border border-gray-200 border-l-4 ${visual.borde} ${visual.fondo} shadow-sm transition hover:-translate-y-0.5 hover:shadow-md`}
    >
      <div className="p-4">

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-extrabold leading-snug text-gray-900">
              {venta.nombre_cliente || venta.rut_cliente}
            </p>

            <p className="mt-1 text-[11px] text-gray-400">
              RUT {venta.rut_cliente || "—"}
            </p>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <span
              className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[10px] font-bold ${
                ESTADO_BADGE[venta.estado_instalacion] ||
                "bg-gray-100 text-gray-500"
              }`}
            >
              {ESTADO_LABEL[venta.estado_instalacion] ||
                venta.estado_instalacion}
            </span>

            {activoPago && (
              <span className="whitespace-nowrap rounded-full bg-emerald-100 px-2.5 py-1 text-[9px] font-bold text-emerald-800">
                PAGÓ BOLETA
              </span>
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-gray-100 bg-white/80 px-3 py-2.5">
            <p className="text-[9px] font-bold uppercase tracking-wide text-gray-400">
              Pedido
            </p>

            <p className="mt-1 break-all text-xs font-bold text-gray-800">
              {venta.n_pedido || "—"}
            </p>
          </div>

          <div className="rounded-xl border border-gray-100 bg-white/80 px-3 py-2.5">
            <p className="text-[9px] font-bold uppercase tracking-wide text-gray-400">
              Servicio
            </p>

            <p className="mt-1 text-xs font-semibold text-gray-700">
              {venta.promocion?.nombre || "Sin detalle"}
            </p>
          </div>
        </div>

        <div className="mt-3 rounded-xl border border-blue-100 bg-white/90 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wide text-gray-400">
                Boleta actual
              </p>

              {corteActual ? (
                <p className="mt-1 text-xs font-extrabold text-gray-900">
                  {corteActual.boleta}
                  <span className="ml-1 font-medium text-gray-400">
                    · {NOMBRE_BOLETA[corteActual.boleta] || corteActual.boleta}
                  </span>
                </p>
              ) : (
                <p className="mt-1 text-xs font-semibold text-gray-400">
                  Sin información
                </p>
              )}
            </div>

            {estadoBoleta && (
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${estadoBoleta.clase}`}
              >
                {estadoBoleta.label}
              </span>
            )}
          </div>

          {corteActual && (
            <div className="mt-2 border-t border-gray-100 pt-2">
              {corteActual.estado_pago === "PAGADO" && corteActual.fecha_pago ? (
                <p className="text-[11px] font-semibold text-green-700">
                  Pagada {fechaCorta(corteActual.fecha_pago)}
                </p>
              ) : corteActual.fecha_vencimiento ? (
                <p
                  className={`text-[11px] font-semibold ${
                    fechaVencida(corteActual.fecha_vencimiento)
                      ? "text-red-600"
                      : "text-gray-600"
                  }`}
                >
                  {fechaVencida(corteActual.fecha_vencimiento)
                    ? "⚠ Venció"
                    : "Vence"}{" "}
                  {fechaCorta(corteActual.fecha_vencimiento)}
                </p>
              ) : (
                <p className="text-[11px] text-gray-400">
                  Sin fecha de vencimiento
                </p>
              )}

              {corteActual.estado_calculado === "FUERA_MEDICION" && (
                <p className="mt-1 text-[10px] font-semibold text-blue-600">
                  Fuera de medición
                </p>
              )}
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => onDetalle?.(venta.id)}
          className="mt-3 flex min-h-10 w-full items-center justify-center rounded-xl border border-gray-200 bg-white px-3 text-xs font-semibold text-gray-700 transition hover:bg-gray-50 active:scale-[0.99]"
        >
          Ver historial y boletas →
        </button>

        {venta.telefono_cliente ? (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() =>
                handleClick("LLAMADA", telHref(venta.telefono_cliente))
              }
              disabled={enviando === "LLAMADA"}
              className="min-h-11 rounded-xl border border-green-200 bg-white px-3 text-xs font-bold text-green-700 transition hover:bg-green-50 disabled:opacity-60"
            >
              {enviando === "LLAMADA" ? "Abriendo…" : "📞 Llamar"}
            </button>

            <button
              type="button"
              onClick={() =>
                handleClick(
                  "WHATSAPP",
                  whatsappHref(venta.telefono_cliente)
                )
              }
              disabled={enviando === "WHATSAPP"}
              className="min-h-11 rounded-xl bg-green-600 px-3 text-xs font-bold text-white shadow-sm transition hover:bg-green-700 disabled:opacity-60"
            >
              {enviando === "WHATSAPP"
                ? "Abriendo…"
                : "WhatsApp"}
            </button>
          </div>
        ) : (
          <div className="mt-3 rounded-xl bg-gray-100 px-3 py-3 text-center">
            <p className="text-[11px] font-medium text-gray-400">
              Sin teléfono registrado
            </p>
          </div>
        )}
      </div>
    </article>
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

function ResumenHoyCard({ titulo, valor, detalle, tono = "gris" }) {
  const tonos = {
    gris: "border-gray-200 bg-white text-gray-900",
    verde: "border-green-100 bg-green-50 text-green-800",
    azul: "border-blue-100 bg-blue-50 text-blue-800",
    naranja: "border-orange-100 bg-orange-50 text-orange-800",
    rojo: "border-red-100 bg-red-50 text-red-800",
  };

  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${tonos[tono] || tonos.gris}`}>
      <p className="text-[10px] font-bold uppercase tracking-wide opacity-70">{titulo}</p>
      <p className="mt-2 text-2xl font-extrabold tracking-tight">{valor}</p>
      <p className="mt-1 text-[11px] leading-snug opacity-80">{detalle}</p>
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
  const [tab, setTab] = useState("resumen");
  const [cortes, setCortes] = useState(null);
  const [historicoKpi, setHistoricoKpi] = useState([]);
  const [perfilKpi, setPerfilKpi] = useState("REGULAR");
  const [honorarios, setHonorarios] = useState(null);
  const [produccionMes, setProduccionMes] = useState(null);
  const [produccionActual, setProduccionActual] = useState(null);
  const [resumenMes, setResumenMes] = useState(null);
  const [mesActual, setMesActual] = useState(mesCalendario(0));
  const [mesAnterior, setMesAnterior] = useState(mesCalendario(-1));
  const [clientesActuales, setClientesActuales] = useState(null);
  const [clientesAnteriores, setClientesAnteriores] = useState(null);
  const [clientesActivosActuales, setClientesActivosActuales] = useState(null);
  const [clientesActivosAnteriores, setClientesActivosAnteriores] = useState(null);
  const [mesClientes, setMesClientes] = useState("ACTUAL");
  const [fechaVencimientoSeleccionada, setFechaVencimientoSeleccionada] = useState(null);
  const [cortesB1, setCortesB1] = useState(null);
  const [errorCortesB1, setErrorCortesB1] = useState("");
  const [filtroClientes, setFiltroClientes] = useState("TODOS_ACTIVOS");
  const [ordenClientes, setOrdenClientes] = useState("NOMBRE");
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
      setProduccionActual(data.produccion_actual || null);
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

  const mesB1 = mesClientes === "ACTUAL" ? mesActual : mesAnterior;

  useEffect(() => {
    setFechaVencimientoSeleccionada(null);
  }, [mesB1]);

  useEffect(() => {
    let vigente = true;
    setCortesB1(null);
    setErrorCortesB1("");

    fetchCortesB1Pendientes(mesB1)
      .then((datos) => {
        if (vigente) setCortesB1(datos);
      })
      .catch(() => {
        if (vigente) {
          setCortesB1([]);
          setErrorCortesB1("No se pudieron consultar los vencimientos B1.");
        }
      });

    return () => {
      vigente = false;
    };
  }, [mesB1]);

  const clientesMes = mesClientes === "ACTUAL" ? clientesActuales : clientesAnteriores;
  const clientesActivosMes = mesClientes === "ACTUAL" ? clientesActivosActuales : clientesActivosAnteriores;
  const mesSeleccionado = mesClientes === "ACTUAL" ? mesActual : mesAnterior;
  const boletaActivaMes = (cortes || []).find((c) => c.mes_ano === mesSeleccionado)?.boleta || null;
  const q = normalizarBusqueda(busqueda);

  const motivosPendienteComercial = useMemo(() => {
    const conteo = new Map();

    for (const venta of clientesMes || []) {
      if (venta.estado_instalacion !== "PENDIENTE_COMERCIAL") continue;

      const motivo =
        String(venta.motivo_pendiente || "").trim() ||
        "Sin motivo informado";

      conteo.set(motivo, (conteo.get(motivo) || 0) + 1);
    }

    return [...conteo.entries()]
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [clientesMes]);

  const clientesFiltrados = useMemo(() => {
    const base =
      filtroClientes === "ACTIVOS_PAGO"
        ? (clientesActivosMes || [])
        : (clientesMes || []);

    return base.filter((venta) => {
      if (
        ["TODOS_ACTIVOS", "NUEVOS"].includes(filtroClientes) &&
        venta.estado_instalacion === "ANULADO"
      ) {
        return false;
      }

      if (
        !["TODOS_ACTIVOS", "NUEVOS", "ACTIVOS_PAGO"].includes(filtroClientes) &&
        venta.estado_instalacion !== filtroClientes
      ) {
        return false;
      }

      if (!q) return true;

      const texto = normalizarBusqueda(
        [venta.nombre_cliente, venta.rut_cliente, venta.n_pedido]
          .filter(Boolean)
          .join(" ")
      );

      return q
        .split(/\s+/)
        .every((parte) => texto.includes(parte));
    }).sort((a, b) => {
      if (ordenClientes === "FECHA_VENTA") return String(b.fecha_venta || "").localeCompare(String(a.fecha_venta || ""));
      if (ordenClientes === "ESTADO") return String(a.estado_instalacion || "").localeCompare(String(b.estado_instalacion || ""));
      return String(a.nombre_cliente || "").localeCompare(String(b.nombre_cliente || ""), "es");
    });
  }, [clientesMes, clientesActivosMes, filtroClientes, q, ordenClientes]);

  const conteosClientes = useMemo(() => {
    const base = clientesMes || [];

    return {
      NUEVOS: base.filter((v) => v.estado_instalacion !== "ANULADO").length,
      TODOS_ACTIVOS: base.filter(
        (v) => v.estado_instalacion !== "ANULADO"
      ).length,
      INSTALADO: base.filter(
        (v) => v.estado_instalacion === "INSTALADO"
      ).length,
      PENDIENTE_INSTALACION: base.filter(
        (v) => v.estado_instalacion === "PENDIENTE_INSTALACION"
      ).length,
      PENDIENTE_COMERCIAL: base.filter(
        (v) => v.estado_instalacion === "PENDIENTE_COMERCIAL"
      ).length,
      ANULADO: base.filter(
        (v) => v.estado_instalacion === "ANULADO"
      ).length,
      ACTIVOS_PAGO: (clientesActivosMes || []).length,
    };
  }, [clientesMes, clientesActivosMes]);

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
  const tieneKpiMesActual = (cortes || []).some((c) => c.mes_ano === mesActual);
  const mesCalidadPendiente = cortes !== null && !tieneKpiMesActual ? mesActual : null;
  const completadas = (clientesActuales || []).filter((v) => v.estado_instalacion === "INSTALADO");
  const kpiCalidad = Number(cortePrincipal?.pct_cumplimiento || 0);
  const metaCalidad = Number(cortePrincipal?.meta_pct || 0);
  const tieneMetaCalidad = cortePrincipal?.meta_definida !== false && metaCalidad > 0;
  const cumpleCalidad = cortePrincipal?.tiene_datos !== false && tieneMetaCalidad && kpiCalidad >= metaCalidad;
  const rguFijoVendidos = produccionMes?.rgu_fijo_vendidos ?? produccionMes?.fija?.rgu_total_base_vigente ?? produccionMes?.kpi_fijo_rgu ?? 0;
  const rguFijoOperativos = produccionMes?.rgu_fijo_gestionables ?? produccionMes?.fija?.total_control ?? 0;
  const ventasFijo = produccionMes?.ventas_fijo ?? produccionMes?.fija?.total_base_vigente ?? 0;
  const rguFijoAnulados = produccionMes?.rgu_fijo_anulados ?? produccionMes?.fija?.anuladas ?? 0;
  const clientesPorVencer = accionables?.por_vencer?.clientes || 0;
  const clientesHoy = accionables?.vence_hoy?.clientes || 0;
  const clientesVencidaGestionable = accionables?.vencida_gestionable?.clientes || 0;
  const clientesFueraPlazo = accionables?.vencida?.clientes || 0;

  const rguPorVencer = accionables?.por_vencer?.rgu || 0;
  const rguHoy = accionables?.vence_hoy?.rgu || 0;
  const rguVencidaGestionable = accionables?.vencida_gestionable?.rgu || 0;
  const rguFueraPlazo = accionables?.vencida?.rgu || 0;

  const clientesGestionarAhora = clientesHoy + clientesVencidaGestionable;
  const rguGestionarAhora = rguHoy + rguVencidaGestionable;
  const rguPendientes = cortePrincipal?.pendientes || 0;
  const mensajeCumplimiento = !cortePrincipal || cortePrincipal?.tiene_datos === false
    ? "Claro todavía no informa una medición vigente para este período."
    : perfilKpi === "HONORARIOS"
      ? `KPI real de pago ${kpiCalidad.toFixed(2)}%. Meta Honorarios pendiente.`
      : cumpleCalidad
        ? `Vas cumpliendo la meta ESACOM de ${metaCalidad.toFixed(0)}%.`
        : `Todavía faltan ${cortePrincipal?.faltan_para_meta || 0} RGU para llegar a la meta ESACOM.`;

  return (
    <Layout titulo="Mi Portal" items={[{ label: "Accionables", to: "/accionables" }]}>
      <section className="mb-5 rounded-3xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm" aria-label="Buscar mis clientes">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-extrabold text-esacom-ink">Busca tus clientes</h2>
            </div>
            <p className="mt-1 text-xs text-gray-500">Escribe el RUT o el nombre. Busca en tu cartera del mes actual/anterior e incluye clientes activos por pago.</p>
          </div>
          <button type="button" onClick={actualizarTodo} disabled={actualizando} className="shrink-0 rounded-xl border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            {actualizando ? "Actualizando…" : "↻ Actualizar"}
          </button>
        </div>
        <div className="relative mt-4">
          <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar cliente por nombre, RUT o número de pedido…" className="w-full min-h-12 rounded-2xl border border-gray-200 bg-gray-50 px-4 pr-10 text-sm outline-none focus:border-esacom-lime focus:ring-2 focus:ring-esacom-lime/20" />
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

      <div className="sticky top-[57px] z-20 -mx-3 mb-5 bg-gray-50/95 px-3 py-2 backdrop-blur sm:static sm:mx-0 sm:bg-transparent sm:px-0 sm:py-0 sm:backdrop-blur-0">
        <div className="grid grid-cols-5 gap-1 rounded-2xl border border-gray-200 bg-white p-1 shadow-sm sm:border-0 sm:bg-transparent sm:shadow-none">
          {[
            ["resumen", "Resumen"],
            ["kpi", "Mi KPI"],
            ["clientes", "Mis Clientes"],
            ["historico", "Histórico"],
            ["completadas", "Completadas"],
          ].map(([key, label]) => (
            <button key={key} onClick={() => setTab(key)} className={`rounded-xl px-1 py-2.5 text-[10px] transition-colors sm:px-4 sm:text-sm ${tab === key ? "bg-esacom-lime-light font-semibold text-esacom-ink" : "text-gray-500 hover:text-esacom-ink"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === "resumen" && (
        <>
      <section className="mb-5 rounded-2xl border border-lime-200 bg-gradient-to-r from-lime-50 to-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-extrabold text-gray-900">Tus ventas y clientes, en un solo lugar</h2>
            <p className="mt-1 text-xs text-gray-600">Revisa quién está instalado, pendiente de instalación o requiere gestión comercial.</p>
          </div>
          <button type="button" onClick={() => { setTab("clientes"); setFiltroClientes("TODOS_ACTIVOS"); }} className="min-h-11 shrink-0 rounded-xl bg-lime-600 px-5 text-sm font-bold text-white shadow-sm transition hover:bg-lime-700">Ver estado comercial →</button>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-white p-3 text-center"><strong className="block text-xl font-black text-green-800">{conteosClientes.INSTALADO}</strong><span className="text-[10px] font-semibold text-gray-600">Instalados</span></div>
          <div className="rounded-xl bg-white p-3 text-center"><strong className="block text-xl font-black text-orange-700">{conteosClientes.PENDIENTE_INSTALACION}</strong><span className="text-[10px] font-semibold text-gray-600">Pend. instalación</span></div>
          <div className="rounded-xl bg-white p-3 text-center"><strong className="block text-xl font-black text-blue-700">{conteosClientes.PENDIENTE_COMERCIAL}</strong><span className="text-[10px] font-semibold text-gray-600">Pend. comercial</span></div>
        </div>
      </section>
      <section className="mb-5" aria-labelledby="resumen-hoy">
        <div className="mb-3">
          <h2
            id="resumen-hoy"
            className="text-lg font-extrabold tracking-tight text-esacom-ink"
          >
            Qué debes hacer hoy
          </h2>
          <p className="text-xs text-gray-500">
            Primero gestiona los casos urgentes. Después anticipa los próximos pagos.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">

          {/* GESTIONAR AHORA */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            clientesGestionarAhora > 0
              ? "border-orange-200 bg-orange-50"
              : "border-gray-200 bg-white"
          }`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-orange-700">
              Gestionar ahora
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {clientesGestionarAhora}
              <span className="ml-2 text-sm font-semibold text-gray-500">
                {clientesGestionarAhora === 1 ? "cliente" : "clientes"}
              </span>
            </p>

            <p className="mt-1 text-xs text-gray-600">
              {rguGestionarAhora} RGU requieren atención inmediata.
            </p>

            <p className="mt-2 text-[11px] text-gray-500">
              {clientesHoy} vencen hoy · {clientesVencidaGestionable} están vencidos pero aún dentro de la ventana de pago.
            </p>

            <a
              href="/accionables?estado=vencida_gestionable"
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-orange-600 px-3 text-xs font-bold text-white transition hover:bg-orange-700"
            >
              Gestionar ahora →
            </a>
          </div>

          {/* ANTICIPAR PAGOS */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            clientesPorVencer > 0
              ? "border-blue-200 bg-blue-50"
              : "border-gray-200 bg-white"
          }`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-blue-700">
              Anticipar pagos
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {clientesPorVencer}
              <span className="ml-2 text-sm font-semibold text-gray-500">
                {clientesPorVencer === 1 ? "cliente" : "clientes"}
              </span>
            </p>

            <p className="mt-1 text-xs text-gray-600">
              {rguPorVencer} RGU todavía no vencen.
            </p>

            <p className="mt-2 text-[11px] text-gray-500">
              Contáctalos antes del vencimiento para aumentar la probabilidad de pago.
            </p>

            <a
              href="/accionables?estado=por_vencer"
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-blue-600 px-3 text-xs font-bold text-white transition hover:bg-blue-700"
            >
              Ver clientes →
            </a>
          </div>

          {/* KPI */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            cumpleCalidad
              ? "border-green-200 bg-green-50"
              : "border-red-200 bg-red-50"
          }`}>
            <p className={`text-[10px] font-extrabold uppercase tracking-wide ${
              cumpleCalidad ? "text-green-700" : "text-red-700"
            }`}>
              Tu KPI
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {!cortePrincipal || cortePrincipal?.tiene_datos === false
                ? "Sin medición"
                : `${kpiCalidad.toFixed(2)}%`}
            </p>

            <p className="mt-1 text-xs text-gray-600">
              {mensajeCumplimiento}
            </p>

            <button
              type="button"
              onClick={() => setTab("kpi")}
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-gray-200 bg-white px-3 text-xs font-bold text-gray-700 transition hover:bg-gray-50"
            >
              Ver Mi KPI →
            </button>
          </div>

          {/* FUERA DE PLAZO */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            clientesFueraPlazo > 0
              ? "border-red-200 bg-red-50"
              : "border-gray-200 bg-white"
          }`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-red-700">
              Fuera de plazo
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {clientesFueraPlazo}
              <span className="ml-2 text-sm font-semibold text-gray-500">
                {clientesFueraPlazo === 1 ? "cliente" : "clientes"}
              </span>
            </p>

            <p className="mt-1 text-xs text-gray-600">
              {rguFueraPlazo} RGU superaron la ventana de +8 días.
            </p>

            <p className="mt-2 text-[11px] text-gray-500">
              Se mantienen visibles para seguimiento y trazabilidad.
            </p>

            <a
              href="/accionables?estado=vencida"
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-red-200 bg-white px-3 text-xs font-bold text-red-700 transition hover:bg-red-50"
            >
              Ver casos →
            </a>
          </div>

        </div>

        <div className="mt-3 rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-[11px] text-blue-800">
          <strong>Regla simple:</strong> primero atiende los vencimientos urgentes,
          luego anticipa los próximos pagos. El KPI se actualiza según la información
          reportada por Claro.
        </div>
      </section>

      <section className="mb-5" aria-labelledby="produccion-esacom">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="produccion-esacom" className="text-lg font-extrabold tracking-tight text-esacom-ink">Producción del mes · {nombreMes(mesActual)}</h2>
            <p className="text-xs text-gray-500">Solo ventas del mes calendario: Fijo por RGU y Móvil por portadas efectivas vendidas en este período. Tu Calidad Claro se detalla en “Mi KPI”.</p>
          </div>
          <span className="text-[10px] font-semibold text-green-700">Fuente oficial: ESACOM</span>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <IndicadorPrincipal
            label={`Ventas Fijo · ${nombreMes(mesActual)}`}
            valor={`${rguFijoVendidos} RGU vendidos`}
            detalle={`${ventasFijo} ventas · ${rguFijoOperativos} RGU operativos · ${rguFijoAnulados} RGU ${rguFijoAnulados === 1 ? "anulado" : "anulados"}`}
            tono="verde"
          />
          <IndicadorPrincipal
            label={`Portadas Móvil · ${nombreMes(mesActual)}`}
            valor={`${produccionMes?.kpi_movil_portadas ?? 0} portadas`}
            detalle={`Del mes · Principal ${produccionMes?.movil?.principal ?? 0} · Adicional ${produccionMes?.movil?.adicional ?? 0}`}
            tono="lima"
          />
        </div>

        <div className="mt-3 flex flex-col gap-1 rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-[11px] text-blue-800 sm:flex-row sm:items-center sm:justify-between">
          <span><strong>{nombreMes(mesActual)}</strong>: ventas Fijo y RGU del mes según ESACOM.</span>
          <span><strong>{cortePrincipal ? nombreMes(cortePrincipal.mes_ano) : "Calidad"}</strong>: período que Claro está midiendo actualmente.</span>
        </div>
      </section>

      <section
        className="mb-5 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"
        aria-labelledby="control-operativo-esacom"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2
              id="control-operativo-esacom"
              className="text-sm font-extrabold text-gray-900"
            >
              Control operativo hoy
            </h2>
            <p className="mt-0.5 text-[10px] text-gray-400">
              Estado vigente según ESACOM.
            </p>
          </div>

          <span className="rounded-full bg-green-50 px-2.5 py-1 text-[9px] font-bold text-green-700">
            ESACOM
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">

          <div className="rounded-xl bg-green-50 px-3 py-3">
            <p className="text-[9px] font-bold uppercase text-green-700">
              Fijo completado
            </p>
            <p className="mt-1 text-xl font-black text-gray-900">
              {produccionActual?.rgu_fijo_completados || 0}
              <span className="ml-1 text-[11px] font-semibold text-gray-500">
                RGU
              </span>
            </p>
          </div>

          <div className="rounded-xl bg-gray-50 px-3 py-3">
            <p className="text-[9px] font-bold uppercase text-gray-500">
              Pend. instalación
            </p>
            <p className="mt-1 text-xl font-black text-gray-900">
              {produccionActual?.rgu_fijo_pendiente_instalacion || 0}
              <span className="ml-1 text-[11px] font-semibold text-gray-500">
                RGU
              </span>
            </p>
          </div>

          <div className="rounded-xl bg-blue-50 px-3 py-3">
            <p className="text-[9px] font-bold uppercase text-blue-700">
              Móvil efectivo
            </p>
            <p className="mt-1 text-xl font-black text-gray-900">
              {produccionActual?.kpi_movil_portadas || 0}
              <span className="ml-1 text-[11px] font-semibold text-gray-500">
                portadas
              </span>
            </p>
          </div>

          <div className="rounded-xl bg-orange-50 px-3 py-3">
            <p className="text-[9px] font-bold uppercase text-orange-700">
              Móvil por activar
            </p>
            <p className="mt-1 text-xl font-black text-gray-900">
              {produccionActual?.movil_pendiente_activacion || 0}
            </p>
          </div>

        </div>
      </section>
        </>
      )}

      {error && <p className="mb-4 rounded-lg bg-esacom-red-light px-4 py-3 text-sm text-esacom-red">{error}</p>}

      {tab === "kpi" && (
        <>
          {cortes === null && <div className="h-48 animate-pulse rounded-xl bg-gray-100" />}
          {cortes && (
            <div>
              <div className="mb-3">
                <h2 className="text-base font-extrabold text-gray-900">{perfilKpi === "HONORARIOS" ? "KPI Calidad Honorarios en curso" : "KPI Calidad en curso"}</h2>
                <p className="text-xs text-gray-500">{perfilKpi === "HONORARIOS" ? "Se muestra el porcentaje real de pago informado por Claro. La meta Honorarios permanece separada y pendiente de definición por Gerencia." : "Pueden coexistir varias camadas en AVANCE. Un mes solo pasa a Histórico cuando Claro envía un CIERRE oficial."}</p>
              </div>
              {perfilKpi === "HONORARIOS" && (
                <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <p className="text-xs font-bold text-amber-900">Perfil Honorarios · medición independiente del KPI Regular</p>
                  <p className="mt-1 text-[11px] text-amber-800">No se aplica la meta 85/83/80 ni se informa Cumple/No cumple hasta que Gerencia defina la meta Honorarios. Tus ventas actuales siguen viniendo de ESACOM.</p>
                </div>
              )}
              {mesCalidadPendiente && (
                <div className="mb-4 max-w-2xl rounded-2xl border border-l-4 border-blue-200 border-l-blue-500 bg-white p-4 shadow-sm sm:p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">
                        {nombreMes(mesCalidadPendiente)}
                      </p>
                      <p className="mt-1 text-xs text-gray-400">
                        Calidad de pago · primera boleta B1
                      </p>
                    </div>
                    <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-700">
                      MES ACTUAL
                    </span>
                  </div>

                  <div className="mt-4 rounded-xl bg-blue-50/60 p-4">
                    <p className="text-base font-extrabold text-blue-900">
                      Aún sin medición B1 de Claro
                    </p>
                    <p className="mt-2 text-xs leading-relaxed text-blue-800">
                      Tu producción de {nombreMes(mesCalidadPendiente)} ya está disponible.
                      El KPI de Calidad aparecerá cuando Claro entregue el primer avance
                      correspondiente a esta camada.
                    </p>
                  </div>
                </div>
              )}
              <div className="max-w-2xl">{cortes.length ? cortes.map((c) => <KpiCard key={`${c.mes_ano}-${c.boleta}`} corte={c} />) : <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">Aún no existe una medición de Calidad en curso para tu cartera.</div>}</div>
            </div>
          )}
        </>
      )}

      {tab === "clientes" && (
        <>
          <section className="mb-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-base font-extrabold text-gray-900">
                  Mis clientes · {nombreMes(mesSeleccionado)}
                </p>

                <p className="mt-1 text-xs text-gray-500">
                  Revisa rápidamente el estado de tus clientes y entra directo a los que requieren seguimiento.
                </p>
              </div>

              <div className="flex rounded-xl bg-gray-100 p-1">
                <button
                  type="button"
                  onClick={() => { setMesClientes("ACTUAL"); setFechaVencimientoSeleccionada(null); }}
                  className={`rounded-lg px-4 py-2 text-xs font-semibold ${
                    mesClientes === "ACTUAL"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500"
                  }`}
                >
                  Mes actual
                </button>

                <button
                  type="button"
                  onClick={() => { setMesClientes("ANTERIOR"); setFechaVencimientoSeleccionada(null); }}
                  className={`rounded-lg px-4 py-2 text-xs font-semibold ${
                    mesClientes === "ANTERIOR"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500"
                  }`}
                >
                  Mes anterior
                </button>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-lime-200 bg-lime-50/70 p-3 sm:p-4">
              <p className="text-xs font-extrabold text-lime-950">Estado comercial de tu cartera</p>
              <p className="mt-1 text-xs text-lime-900/80">Selecciona una tarjeta para ver los clientes. «Del mes» muestra ventas vigentes; «Pagaron» es un filtro de pago que puede coincidir con otros estados.</p>
            </div>
            <div className="mt-3">
              <TarjetasEstadoComercial
                activo={filtroClientes}
                onSeleccionar={(key) => { setFiltroClientes(key); setFechaVencimientoSeleccionada(null); }}
                items={[
                  { key: "NUEVOS", label: "Clientes del mes", valor: conteosClientes.NUEVOS, detalle: "Ventas vigentes del período", tono: "lima", icono: "＋" },
                  { key: "INSTALADO", label: "Instalados", valor: conteosClientes.INSTALADO, detalle: "Servicio completado", tono: "verde", icono: "✓" },
                  { key: "PENDIENTE_INSTALACION", label: "Pend. instalación", valor: conteosClientes.PENDIENTE_INSTALACION, detalle: "Esperan instalación", tono: "naranja", icono: "⌛" },
                  { key: "PENDIENTE_COMERCIAL", label: "Pend. comercial", valor: conteosClientes.PENDIENTE_COMERCIAL, detalle: "Requieren seguimiento", tono: "azul", icono: "◎" },
                  { key: "ACTIVOS_PAGO", label: "Pagaron", valor: conteosClientes.ACTIVOS_PAGO, detalle: "Pago informado para boleta vigente", tono: "verde", icono: "$" },
                  { key: "ANULADO", label: "Anulados", valor: conteosClientes.ANULADO, detalle: "No vigentes", tono: "rojo", icono: "✕" },
                ]}
              />
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-gray-200 bg-white p-3">
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => { setFiltroClientes("TODOS_ACTIVOS"); setBusqueda(""); }} className="min-h-10 rounded-xl bg-lime-100 px-3 text-xs font-bold text-lime-950 hover:bg-lime-200">Ver todos los activos</button>
                <button type="button" onClick={() => { setFiltroClientes("PENDIENTE_COMERCIAL"); setBusqueda(""); }} className="min-h-10 rounded-xl bg-blue-50 px-3 text-xs font-bold text-blue-800 hover:bg-blue-100">Gestionar pendientes comerciales</button>
              </div>
              <label className="flex items-center gap-2 text-xs font-semibold text-gray-600">
                Ordenar
                <select aria-label="Ordenar clientes" value={ordenClientes} onChange={(e) => setOrdenClientes(e.target.value)} className="min-h-10 rounded-xl border border-gray-200 bg-white px-3 text-xs text-gray-900">
                  <option value="NOMBRE">Nombre</option>
                  <option value="FECHA_VENTA">Venta más reciente</option>
                  <option value="ESTADO">Estado comercial</option>
                </select>
              </label>
            </div>

            <div className="mt-3 rounded-xl bg-gray-50 px-4 py-3">
              <p className="text-xs font-semibold text-gray-800">
                Mostrando {clientesFiltrados.length}{" "}
                {clientesFiltrados.length === 1 ? "cliente" : "clientes"}
              </p>

              <p className="mt-0.5 text-[10px] text-gray-400">
                {["TODOS_ACTIVOS", "NUEVOS"].includes(filtroClientes) &&
                  "Clientes vigentes del mes, excluyendo anulados."}

                {filtroClientes === "INSTALADO" &&
                  "Clientes que ya tienen instalación completada."}

                {filtroClientes === "PENDIENTE_INSTALACION" &&
                  "Clientes que todavía esperan instalación."}

                {filtroClientes === "PENDIENTE_COMERCIAL" &&
                  "Clientes con gestión comercial pendiente."}

                {filtroClientes === "ACTIVOS_PAGO" &&
                  `Clientes con pago informado para la boleta vigente${
                    boletaActivaMes
                      ? ` (${NOMBRE_BOLETA[boletaActivaMes]})`
                      : ""
                  }.`}

                {filtroClientes === "ANULADO" &&
                  "Clientes anulados del período seleccionado."}
              </p>
            </div>
          </section>

          <div className="mb-4">
            <MotivosPendienteBarChart
              items={motivosPendienteComercial}
              titulo="Pendientes comerciales por motivo"
              subtitulo={`Casos que debes resolver en ${nombreMes(mesSeleccionado)}.`}
            />
          </div>

          <div className="mb-4">
            {cortesB1 === null ? (
              <div className="h-40 animate-pulse rounded-2xl bg-gray-100" />
            ) : errorCortesB1 ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
                {errorCortesB1}
              </div>
            ) : (
              <VencimientoPrimeraBoletaChart
                cortes={cortesB1}
                mesSeleccionado={mesSeleccionado}
                fechaSeleccionada={fechaVencimientoSeleccionada}
                onSeleccionarFecha={setFechaVencimientoSeleccionada}
              />
            )}
          </div>

          {fechaVencimientoSeleccionada && !errorCortesB1 && (
            <section className="mb-5 rounded-2xl border border-blue-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-extrabold text-gray-900">
                    Clientes B1 por gestionar
                  </h3>
                  <p className="text-xs text-gray-500">
                    Vencimiento: {fechaVencimientoSeleccionada.split("-").reverse().join("/")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFechaVencimientoSeleccionada(null)}
                  className="rounded-lg border px-3 py-2 text-xs font-bold text-blue-700"
                >
                  Quitar filtro
                </button>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {(cortesB1 || [])
                  .filter((c) =>
                    c.mes_ano === mesSeleccionado &&
                    c.boleta === "B1" &&
                    c.estado_pago === "PENDIENTE" &&
                    c.venta?.estado_instalacion === "INSTALADO" &&
                    String(c.fecha_vencimiento || "").slice(0, 10) === fechaVencimientoSeleccionada &&
                    Number(c.rgu_kpi ?? c.venta?.rgu_base ?? 0) > 0
                  )
                  .map((c) => (
                    <div key={c.id} className="rounded-xl border border-gray-200 bg-gray-50 p-3">
                      <p className="text-xs font-bold text-gray-900">
                        Pedido: {c.venta?.n_pedido || "Sin número"}
                      </p>
                      <p className="mt-1 text-xs text-gray-600">
                        B1 pendiente · {c.rgu_kpi ?? c.venta?.rgu_base ?? 0} RGU
                      </p>
                      <button
                        type="button"
                        onClick={() => setVentaDetalle(c.venta.id)}
                        className="mt-3 rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-blue-700"
                      >
                        Ver historial y boletas →
                      </button>
                    </div>
                  ))}
              </div>
            </section>
          )}

          {(filtroClientes === "ACTIVOS_PAGO"
            ? clientesActivosMes
            : clientesMes) === null ? (
            <div className="h-64 animate-pulse rounded-2xl bg-gray-100" />
          ) : clientesFiltrados.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center">
              <p className="text-sm font-semibold text-gray-500">
                No hay clientes en esta categoría.
              </p>
              <p className="mt-1 text-xs text-gray-400">
                Prueba otro estado o cambia entre mes actual y mes anterior.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {clientesFiltrados.map((v) => (
                <ClienteCard
                  key={v.id}
                  venta={v}
                  onDetalle={setVentaDetalle}
                  activoPago={filtroClientes === "ACTIVOS_PAGO"}
                  mesSeleccionado={mesSeleccionado}
                  boletaActivaMes={boletaActivaMes}
                />
              ))}
            </div>
          )}
        </>
      )}

      {tab === "historico" && (
        <section>
          <div className="mb-3"><h2 className="text-base font-extrabold text-gray-900">{perfilKpi === "HONORARIOS" ? "Histórico KPI Calidad Honorarios" : "Histórico KPI Calidad Fijo"}</h2><p className="text-xs text-gray-500">{perfilKpi === "HONORARIOS" ? "Muestra tu porcentaje real de pago por mes, sin aplicar una meta Regular. Los cierres quedan congelados." : "Aquí aparecen únicamente meses con CIERRE oficial recibido de Claro. Los AVANCE permanecen en Mi KPI aunque exista una camada más nueva."}</p></div>
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
