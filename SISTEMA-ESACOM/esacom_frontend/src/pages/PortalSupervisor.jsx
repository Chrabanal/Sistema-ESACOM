import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import ClienteDetalleModal from "../components/ClienteDetalleModal";
import TarjetasEstadoComercial from "../components/TarjetasEstadoComercial";
import {
  EstadoVentasDonut,
  RankingKpiBarChart,
  TendenciaKpiChart,
  UrgenciaBarChart,
} from "../components/DashboardCharts";
import { fetchResumenEquipo, fetchVentas } from "../api/apelaciones";
import {
  fetchDashboardKpiCompleto,
  fetchKpiPorEjecutivoCompleto,
  fetchAccionables,
} from "../api/dashboard";


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
  const nombres = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
  ];

  const i = Number(mes) - 1;

  return i >= 0 && i < 12
    ? `${nombres[i]} ${anio}`
    : mesAno || "Mes actual";
}


function fechaHora(valor) {
  if (!valor) return "Sin carga registrada";

  return new Intl.DateTimeFormat("es-CL", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(valor));
}


function corteActual(fila) {
  return (
    (fila?.cortes || []).find((c) => c.boleta === "B1")
    || (fila?.cortes || [])[0]
    || null
  );
}


function tienePoblacionKpi(corte) {
  if (!corte || corte.tiene_datos === false) return false;

  // Regla UX/fidelidad: solo existe medición cuando hay población KPI real
  // en categorías que participan directamente del cálculo visible.
  // S/B, fuera de medición o un total técnico no deben convertir un caso
  // sin medición en 0.00%.
  const poblacionMedible = [
    corte.pagadas,
    corte.pendientes,
    corte.no_pago,
    corte.fuera_plazo,
  ].reduce((acc, valor) => acc + Number(valor || 0), 0);

  return poblacionMedible > 0;
}

function claseKpi(corte) {
  if (!tienePoblacionKpi(corte)) return "text-gray-400";

  const kpi = Number(corte.pct_cumplimiento || 0);
  const meta = Number(corte.meta_pct || 0);

  if (meta && kpi >= meta) return "text-green-700";
  if (meta && kpi >= meta - 10) return "text-amber-600";

  return "text-esacom-red";
}


function TarjetaResumen({
  titulo,
  valor,
  detalle,
  tono = "neutro",
}) {
  const tonos = {
    verde: "border-green-100 bg-green-50 text-green-800",
    azul: "border-blue-100 bg-blue-50 text-blue-800",
    lima: "border-esacom-lime/30 bg-esacom-lime-light text-esacom-ink",
    neutro: "border-gray-200 bg-white text-gray-900",
  };

  return (
    <div
      className={`rounded-2xl border p-4 shadow-sm ${
        tonos[tono] || tonos.neutro
      }`}
    >
      <p className="text-[10px] font-bold uppercase tracking-wide opacity-70">
        {titulo}
      </p>

      <p className="mt-1 text-2xl font-extrabold tracking-tight">
        {valor}
      </p>

      <p className="mt-1 text-[11px] leading-snug opacity-75">
        {detalle}
      </p>
    </div>
  );
}


function FocusCard({ titulo, valor, detalle, tono = "gris" }) {
  const tonos = {
    gris: "border-gray-200 bg-white text-gray-900",
    rojo: "border-red-100 bg-red-50 text-red-800",
    naranja: "border-orange-100 bg-orange-50 text-orange-800",
    azul: "border-blue-100 bg-blue-50 text-blue-800",
    verde: "border-green-100 bg-green-50 text-green-800",
  };

  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${tonos[tono] || tonos.gris}`}>
      <p className="text-[10px] font-bold uppercase tracking-wide opacity-70">{titulo}</p>
      <p className="mt-2 text-2xl font-extrabold tracking-tight">{valor}</p>
      <p className="mt-1 text-[11px] leading-snug opacity-80">{detalle}</p>
    </div>
  );
}


function CalidadEquipo({ corte, ultimaCarga }) {
  if (!tienePoblacionKpi(corte)) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
        Aún no existe una población KPI medible para el equipo en el período activo.
      </div>
    );
  }

  const kpi = Number(corte.pct_cumplimiento || 0);
  const meta = Number(corte.meta_pct || 0);
  const cumple = meta > 0 && kpi >= meta;

  const avance = meta > 0
    ? Math.min((kpi / meta) * 100, 100)
    : Math.min(kpi, 100);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-bold uppercase tracking-wide text-blue-700">
              Calidad del equipo · {nombreMes(corte.mes_ano)}
            </p>

            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[9px] font-bold text-blue-700 ring-1 ring-blue-100">
              EN CURSO
            </span>
          </div>

          <p className="mt-1 text-[11px] text-gray-500">
            Último avance Claro del período actualmente medido.
          </p>
        </div>

        <div className="text-left sm:text-right">
          <p
            className={`text-4xl font-extrabold tracking-tight ${
              cumple ? "text-green-700" : "text-esacom-red"
            }`}
          >
            {kpi.toFixed(2)}%
          </p>

          <p className="text-[11px] font-medium text-gray-600">
            Meta ESACOM {meta.toFixed(0)}%
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
        <div
          className={`rounded-xl p-3 ${
            cumple ? "bg-green-50" : "bg-red-50"
          }`}
        >
          <p className="text-[10px] uppercase text-gray-400">
            Estado
          </p>

          <p
            className={`mt-1 text-base font-extrabold ${
              cumple ? "text-green-800" : "text-red-800"
            }`}
          >
            {cumple ? "✓ Cumple" : "Aún no cumple"}
          </p>
        </div>

        <div className="rounded-xl bg-green-50 p-3">
          <p className="text-[10px] uppercase text-green-700">
            Pago
          </p>

          <p className="mt-1 text-base font-extrabold text-green-800">
            {corte.pagadas || 0} RGU
          </p>
        </div>

        <div className="rounded-xl bg-blue-50 p-3">
          <p className="text-[10px] uppercase text-blue-700">
            Pendiente
          </p>

          <p className="mt-1 text-base font-extrabold text-blue-800">
            {corte.pendientes || 0} RGU
          </p>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-[10px] text-gray-500">
          <span>Avance hacia la meta</span>

          <span>
            {kpi.toFixed(2)}% / {meta.toFixed(0)}%
          </span>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-gray-100">
          <div
            className={`h-full ${
              cumple ? "bg-esacom-green" : "bg-esacom-red"
            }`}
            style={{ width: `${avance}%` }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <div className="rounded-lg bg-red-50 p-2">
          <span className="text-red-700">
            Vencido +8
          </span>

          <strong className="float-right">
            {corte.gestion?.vencido_mas_8 || 0}
          </strong>
        </div>

        <div className="rounded-lg bg-orange-50 p-2">
          <span className="text-orange-700">
            Vencido 0-8
          </span>

          <strong className="float-right">
            {corte.gestion?.vencido_0_8 || 0}
          </strong>
        </div>

        <div className="rounded-lg bg-yellow-50 p-2">
          <span className="text-yellow-700">
            Vence 0-7
          </span>

          <strong className="float-right">
            {corte.gestion?.gestionar_0_7 || 0}
          </strong>
        </div>

        <div className="rounded-lg bg-blue-50 p-2">
          <span className="text-blue-700">
            Vence +8
          </span>

          <strong className="float-right">
            {corte.gestion?.gestionar_8_mas || 0}
          </strong>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-1 border-t border-gray-100 pt-3 text-[10px] text-gray-400 sm:flex-row sm:items-center sm:justify-between">
        <span>
          Último reporte Claro:{" "}
          {ultimaCarga
            ? `${ultimaCarga.dia_reporte || "OTRO"} · corte ${
                ultimaCarga.fecha_corte || "—"
              }`
            : "Sin reporte"}
        </span>

        {corte.valor_informado_claro !== null
          && corte.valor_informado_claro !== undefined && (
          <span>
            Referencia Claro:{" "}
            <strong className="text-blue-700">
              {Number(corte.valor_informado_claro).toFixed(2)}%
            </strong>
          </span>
        )}
      </div>
    </div>
  );
}


function TarjetaHistorico({ corte, cerrado = false }) {
  const kpi = Number(corte?.pct_cumplimiento || 0);
  const meta = Number(corte?.meta_pct || 0);
  const cumple = meta > 0 && kpi >= meta;

  const pago = Number(corte?.pagadas || 0);
  const pendiente = Number(corte?.pendientes || 0);
  const noPago = Number(corte?.no_pago || 0);
  const fueraPlazo = Number(corte?.fuera_plazo || 0);
  const sinBoleta = Number(corte?.sin_boleta || 0);
  const fueraMedicion = Number(corte?.fuera_medicion || 0);
  const total = Number(corte?.total || 0);
  // El cierre puede traer indicadores auxiliares que se solapan con los
  // estados principales. Para conciliar el Total RGU solo usamos categorías
  // exclusivas visibles: Pago + Pendiente + No pago + residual del cierre.
  const sumaPrincipal = pago + pendiente + noPago;
  const otrosEstados = Math.max(total - sumaPrincipal, 0);
  const conciliado = sumaPrincipal + otrosEstados;

  return (
    <div
      className={`rounded-2xl border bg-white p-4 shadow-sm ${
        cerrado
          ? "border-green-200"
          : "border-blue-100"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-extrabold text-gray-900">
            {nombreMes(corte?.mes_ano)}
          </p>

          <span
            className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[9px] font-bold ring-1 ${
              cerrado
                ? "bg-green-50 text-green-700 ring-green-100"
                : "bg-blue-50 text-blue-700 ring-blue-100"
            }`}
          >
            {cerrado ? "CIERRE OFICIAL" : "EN CURSO"}
          </span>
        </div>

        <div className="text-right">
          <p
            className={`text-2xl font-extrabold ${
              cumple
                ? "text-green-700"
                : "text-esacom-red"
            }`}
          >
            {kpi.toFixed(2)}%
          </p>

          <p className="text-[10px] text-gray-400">
            Meta {meta.toFixed(0)}%
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-center text-[10px] sm:grid-cols-4">
        <div className="rounded-lg bg-green-50 p-2">
          <strong className="block text-sm text-green-800">{pago}</strong>
          Pago
        </div>
        <div className="rounded-lg bg-blue-50 p-2">
          <strong className="block text-sm text-blue-800">{pendiente}</strong>
          Pendiente
        </div>
        <div className="rounded-lg bg-red-50 p-2">
          <strong className="block text-sm text-red-800">{noPago}</strong>
          No pago
        </div>
        <div className="rounded-lg bg-orange-50 p-2">
          <strong className="block text-sm text-orange-700">
            {cerrado ? total : fueraPlazo}
          </strong>
          {cerrado ? "Total RGU" : "Fuera plazo"}
        </div>
      </div>

      {cerrado && (
        <div className="mt-3 rounded-xl border border-gray-100 bg-gray-50 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] font-bold uppercase tracking-wide text-gray-500">Conciliación del cierre</p>
            <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${conciliado === total ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>
              {conciliado === total ? "Total explicado" : "Revisar total"}
            </span>
          </div>

          <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] sm:grid-cols-4">
            <span className="rounded-lg bg-white px-2 py-1.5 text-gray-500">Pago <strong className="float-right text-gray-700">{pago}</strong></span>
            <span className="rounded-lg bg-white px-2 py-1.5 text-gray-500">Pendiente <strong className="float-right text-gray-700">{pendiente}</strong></span>
            <span className="rounded-lg bg-white px-2 py-1.5 text-gray-500">No pago <strong className="float-right text-gray-700">{noPago}</strong></span>
            <span className="rounded-lg bg-white px-2 py-1.5 text-gray-500">Otros estados <strong className="float-right text-gray-700">{otrosEstados}</strong></span>
          </div>

          <p className="mt-2 text-[10px] text-gray-500">
            Pago {pago} + Pendiente {pendiente} + No pago {noPago} + Otros estados {otrosEstados} = <strong className="text-gray-700">{conciliado} RGU</strong>.
          </p>

          {(fueraPlazo > 0 || sinBoleta > 0 || fueraMedicion > 0) && (
            <div className="mt-2 border-t border-gray-200 pt-2">
              <p className="text-[9px] font-bold uppercase tracking-wide text-gray-400">Indicadores auxiliares · no se suman al total</p>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-gray-500">
                <span>Fuera plazo <strong className="text-gray-700">{fueraPlazo}</strong></span>
                <span>S/B <strong className="text-gray-700">{sinBoleta}</strong></span>
                <span>Fuera medición <strong className="text-gray-700">{fueraMedicion}</strong></span>
              </div>
              <p className="mt-1 text-[9px] text-gray-400">Estos indicadores pueden solaparse con los estados principales del cierre.</p>
            </div>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px]">
        <span className="text-gray-400">
          Corte Claro {corte?.fecha_corte || "—"}
        </span>

        {cerrado && (
          <span className="font-semibold text-green-700">
            Congelado
          </span>
        )}
      </div>
    </div>
  );
}


export default function PortalSupervisor() {
  const [resumen, setResumen] = useState(null);
  const [ventas, setVentas] = useState(null);

  const [kpiEquipo, setKpiEquipo] = useState([]);
  const [historicoKpi, setHistoricoKpi] = useState([]);

  const [ultimaCarga, setUltimaCarga] = useState(null);
  const [kpiEjecutivos, setKpiEjecutivos] = useState([]);
  const [honorariosEquipo, setHonorariosEquipo] = useState([]);
  const [snapshotEjecutivos, setSnapshotEjecutivos] = useState(null);
  const [accionablesEquipo, setAccionablesEquipo] = useState(null);

  const [estado, setEstado] = useState("");
  const [ordenCartera, setOrdenCartera] = useState("FECHA");
  const [perfilKpi, setPerfilKpi] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [busquedaEjecutivo, setBusquedaEjecutivo] = useState("");
  const [error, setError] = useState("");
  const [ejecutivoFiltro, setEjecutivoFiltro] = useState("");
  const [ventaDetalle, setVentaDetalle] = useState(null);
  const [actualizando, setActualizando] = useState(false);
  const [refrescadoEn, setRefrescadoEn] = useState(null);
  const [periodoCartera, setPeriodoCartera] = useState("MES_ACTUAL");
  const [vistaSupervisor, setVistaSupervisor] = useState("resumen");


  const cargarPrincipal = useCallback(
    async ({
      silencioso = false,
      incluirVentas = false,
    } = {}) => {
      if (!silencioso) {
        setActualizando(true);
      }

      try {
        const peticiones = [
          fetchResumenEquipo(),
          fetchDashboardKpiCompleto(),
          fetchKpiPorEjecutivoCompleto(),
          fetchAccionables(),
        ];

        if (incluirVentas) {
          const params = {
            page_size: 1000,
          };

          if (
            periodoCartera === "MES_ACTUAL"
            && resumen?.mes_actual
          ) {
            params.camada = resumen.mes_actual;
          }

          peticiones.push(fetchVentas(params));
        }

        const [
          r,
          kpiData,
          ejecutivosData,
          accionablesData,
          ventasData,
        ] = await Promise.all(peticiones);

        setResumen(r);

        setKpiEquipo(kpiData.cortes || []);
        setHistoricoKpi(kpiData.historico_kpi || []);

        setUltimaCarga(kpiData.ultima_carga || null);

        setKpiEjecutivos(
          ejecutivosData.ejecutivos || [],
        );

        setHonorariosEquipo(
          ejecutivosData.honorarios || [],
        );

        setSnapshotEjecutivos(
          ejecutivosData.snapshot || null,
        );

        setAccionablesEquipo(
          accionablesData || null,
        );

        if (incluirVentas) {
          setVentas(ventasData || []);
        }

        setRefrescadoEn(new Date());
        setError("");
      } catch {
        if (!silencioso) {
          setError(
            "No se pudo actualizar el resumen del equipo.",
          );
        }
      } finally {
        if (!silencioso) {
          setActualizando(false);
        }
      }
    },
    [
      estado,
      periodoCartera,
      resumen?.mes_actual,
    ],
  );


  useEffect(() => {
    cargarPrincipal({
      incluirVentas: true,
    });

    const timer = window.setInterval(
      () =>
        cargarPrincipal({
          silencioso: true,
          incluirVentas: true,
        }),
      60_000,
    );

    const onFocus = () =>
      cargarPrincipal({
        silencioso: true,
        incluirVentas: true,
      });

    window.addEventListener("focus", onFocus);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener(
        "focus",
        onFocus,
      );
    };
  }, [cargarPrincipal]);


  useEffect(() => {
    const params = {
      page_size: 1000,
    };

    if (
      periodoCartera === "MES_ACTUAL"
      && resumen?.mes_actual
    ) {
      params.camada = resumen.mes_actual;
    }

    fetchVentas(params)
      .then((data) =>
        setVentas(data || []),
      )
      .catch(() =>
        setError(
          "No se pudo cargar la cartera del equipo.",
        ),
      );
  }, [
    estado,
    periodoCartera,
    resumen?.mes_actual,
  ]);


  const calidadActual =
    (kpiEquipo || [])[0] || null;

  const mesActual =
    resumen?.mes_actual || "";

  const prodEquipo =
    resumen?.produccion_equipo_mes || null;

  const prodPropia =
    resumen?.produccion_supervisor_mes || null;

  const controlEquipo =
    resumen?.control_operativo_equipo || null;

  const controlPropia =
    resumen?.control_operativo_supervisor || null;

  const actividadEquipo =
    resumen?.actividad_equipo_mes || null;


  const ranking = useMemo(() => {
    const q = busquedaEjecutivo
      .trim()
      .toLowerCase();

    return [...(kpiEjecutivos || [])]
      .filter((fila) => {
        if (!q) return true;

        const e = fila.ejecutivo || {};

        return `${e.nombre || ""} ${
          e.rut || ""
        } ${
          e.equipo || ""
        }`
          .toLowerCase()
          .includes(q);
      })
      .sort((a, b) => {
        const ca = corteActual(a);
        const cb = corteActual(b);
        const ma = tienePoblacionKpi(ca);
        const mb = tienePoblacionKpi(cb);

        if (ma !== mb) return ma ? -1 : 1;
        if (!ma && !mb) {
          return String(a?.ejecutivo?.nombre || "").localeCompare(String(b?.ejecutivo?.nombre || ""));
        }

        return Number(ca?.pct_cumplimiento || 0) - Number(cb?.pct_cumplimiento || 0);
      });
  }, [
    kpiEjecutivos,
    busquedaEjecutivo,
  ]);


  const honorariosFiltrados =
    useMemo(() => {
      const q = busquedaEjecutivo
        .trim()
        .toLowerCase();

      return [...(honorariosEquipo || [])]
        .filter((fila) => {
          if (!q) return true;

          const e =
            fila.ejecutivo || {};

          return `${e.nombre || ""} ${
            e.rut || ""
          } ${
            e.equipo || ""
          }`
            .toLowerCase()
            .includes(q);
        });
    }, [
      honorariosEquipo,
      busquedaEjecutivo,
    ]);


  const ejecutivoSeleccionado =
    useMemo(
      () =>
        (kpiEjecutivos || []).find(
          (x) =>
            String(
              x.ejecutivo?.id,
            )
            === String(
              ejecutivoFiltro,
            ),
        )
        || (honorariosEquipo || []).find(
          (x) =>
            String(
              x.ejecutivo?.id,
            )
            === String(
              ejecutivoFiltro,
            ),
        )
        || null,
      [
        kpiEjecutivos,
        honorariosEquipo,
        ejecutivoFiltro,
      ],
    );


  const conteosEstadoComercial = useMemo(() => {
    const base = (ventas || []).filter((v) => {
      if (ejecutivoFiltro && String(v.ejecutivo?.id || "") !== String(ejecutivoFiltro)) return false;
      if (perfilKpi && (v.ejecutivo?.tipo_kpi || "REGULAR") !== perfilKpi) return false;
      return true;
    });
    return {
      TODOS: base.length,
      NUEVOS: base.filter((v) => v.estado_instalacion !== "ANULADO").length,
      INSTALADO: base.filter((v) => v.estado_instalacion === "INSTALADO").length,
      PENDIENTE_INSTALACION: base.filter((v) => v.estado_instalacion === "PENDIENTE_INSTALACION").length,
      PENDIENTE_COMERCIAL: base.filter((v) => v.estado_instalacion === "PENDIENTE_COMERCIAL").length,
      ANULADO: base.filter((v) => v.estado_instalacion === "ANULADO").length,
    };
  }, [ventas, ejecutivoFiltro, perfilKpi]);

  const ventasFiltradas =
    useMemo(
      () =>
        (ventas || []).filter((v) => {
          if (estado === "NUEVOS" && v.estado_instalacion === "ANULADO") return false;
          if (estado && estado !== "NUEVOS" && v.estado_instalacion !== estado) return false;
          const ownerId =
            v.ejecutivo?.id;

          if (
            ejecutivoFiltro
            && String(
              ownerId || "",
            )
              !== String(
                ejecutivoFiltro,
              )
          ) {
            return false;
          }

          if (
            perfilKpi
            && (
              v.ejecutivo?.tipo_kpi
              || "REGULAR"
            )
              !== perfilKpi
          ) {
            return false;
          }

          if (!busqueda.trim()) {
            return true;
          }

          const q =
            busqueda.toLowerCase();

          return (
            (v.rut_cliente || "")
              .toLowerCase()
              .includes(q)
            || (v.n_pedido || "")
              .toLowerCase()
              .includes(q)
            || (v.nombre_cliente || "")
              .toLowerCase()
              .includes(q)
            || (
              v.ejecutivo?.nombre
              || ""
            )
              .toLowerCase()
              .includes(q)
          );
        }).sort((a, b) => {
          if (ordenCartera === "NOMBRE") return String(a.nombre_cliente || "").localeCompare(String(b.nombre_cliente || ""), "es");
          if (ordenCartera === "ESTADO") return String(a.estado_instalacion || "").localeCompare(String(b.estado_instalacion || ""));
          return String(b.fecha_venta || "").localeCompare(String(a.fecha_venta || ""));
        }),
      [
        ventas,
        ejecutivoFiltro,
        perfilKpi,
        busqueda,
        ordenCartera,
        estado,
      ],
    );


  const propiaDisponible =
    Boolean(
      prodPropia?.disponible,
    );

  const ejecutivosBajoMeta = ranking.filter((fila) => {
    const c = corteActual(fila);
    return tienePoblacionKpi(c) && Number(c.meta_pct || 0) > 0 && Number(c.pct_cumplimiento || 0) < Number(c.meta_pct || 0);
  }).length;

  const ejecutivosSinMedicion = ranking.filter((fila) => !tienePoblacionKpi(corteActual(fila))).length;

  const gestionableEquipo = accionablesEquipo?.vencida_gestionable || {};
  const venceHoyEquipo = accionablesEquipo?.vence_hoy || {};
  const porVencerEquipo = accionablesEquipo?.por_vencer || {};
  const fueraPlazoEquipo = accionablesEquipo?.vencida || {};

  const clientesGestionarAhora =
    Number(gestionableEquipo.clientes || 0) +
    Number(venceHoyEquipo.clientes || 0);

  const rguGestionarAhora =
    Number(gestionableEquipo.rgu || 0) +
    Number(venceHoyEquipo.rgu || 0);

  const casosPendientesInstalacion = actividadEquipo?.pendiente_instalacion || 0;
  const casosPendientesComercial = actividadEquipo?.pendiente_comercial || 0;

  const porcentajeEquipo = calidadActual
    ? Number(calidadActual?.pct_cumplimiento || 0).toFixed(2)
    : "Sin dato";

  const abrirCarteraEjecutivo = (id) => {
    setEjecutivoFiltro(String(id));
    setVistaSupervisor("cartera");
  };


  const prioridadEjecutivos = useMemo(() => {
    const mapa = new Map();

    const obtener = (nombre) => {
      const clave = nombre || "Sin ejecutivo";

      if (!mapa.has(clave)) {
        mapa.set(clave, {
          nombre: clave,
          gestionables: 0,
          hoy: 0,
          porVencer: 0,
          fueraPlazo: 0,
          rguGestionables: 0,
          rguHoy: 0,
          rguPorVencer: 0,
        });
      }

      return mapa.get(clave);
    };

    for (const item of accionablesEquipo?.vencida_gestionable?.items || []) {
      const fila = obtener(item.ejecutivo);
      fila.gestionables += 1;
      fila.rguGestionables += Number(item.rgu || 0);
    }

    for (const item of accionablesEquipo?.vence_hoy?.items || []) {
      const fila = obtener(item.ejecutivo);
      fila.hoy += 1;
      fila.rguHoy += Number(item.rgu || 0);
    }

    for (const item of accionablesEquipo?.por_vencer?.items || []) {
      const fila = obtener(item.ejecutivo);
      fila.porVencer += 1;
      fila.rguPorVencer += Number(item.rgu || 0);
    }

    for (const item of accionablesEquipo?.vencida?.items || []) {
      const fila = obtener(item.ejecutivo);
      fila.fueraPlazo += 1;
    }

    return [...mapa.values()]
      .map((fila) => ({
        ...fila,
        urgentes: fila.gestionables + fila.hoy,
        rguUrgentes: fila.rguGestionables + fila.rguHoy,
      }))
      .filter(
        (fila) =>
          fila.urgentes > 0 ||
          fila.porVencer > 0 ||
          fila.fueraPlazo > 0,
      )
      .sort(
        (a, b) =>
          b.urgentes - a.urgentes ||
          b.hoy - a.hoy ||
          b.porVencer - a.porVencer ||
          a.nombre.localeCompare(b.nombre),
      );
  }, [accionablesEquipo]);

  return (
    <Layout
      titulo="Dashboard Supervisor"
      items={[
        {
          label: "Resumen",
          to: "/supervisor",
        },
        {
          label: "Accionables",
          to: "/accionables",
        },
      ]}
    >
      {error && (
        <p className="mb-4 rounded-lg bg-esacom-red-light px-4 py-3 text-sm text-esacom-red">
          {error}
        </p>
      )}


      <section className="mb-6 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-extrabold text-gray-900">Resumen del equipo</h2>
            </div>

            <p className="mt-1 text-xs text-gray-500">
              <strong>
                {nombreMes(mesActual)}
              </strong>{" "}
              muestra ventas y RGU actuales de
              ESACOM. Calidad se actualiza con
              el período que Claro está
              midiendo.
            </p>

            <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
              <span className="rounded-full bg-green-50 px-2.5 py-1 font-semibold text-green-700 ring-1 ring-green-100">
                ESACOM actualizado: {fechaHora(
                  resumen?.ultima_carga_esacom
                  || resumen?.estado_datos?.esacom?.actualizado_en,
                )}
              </span>
              <span className="rounded-full bg-blue-50 px-2.5 py-1 font-semibold text-blue-700 ring-1 ring-blue-100">
                KPI Claro · corte {ultimaCarga?.fecha_corte || snapshotEjecutivos?.fecha_corte || "Sin corte"}
              </span>
              <span className="rounded-full bg-gray-50 px-2.5 py-1 text-gray-500 ring-1 ring-gray-200">
                Consultado: {refrescadoEn ? fechaHora(refrescadoEn) : "—"}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={() =>
              cargarPrincipal({
                incluirVentas: true,
              })
            }
            disabled={actualizando}
            className="min-h-11 rounded-xl bg-gray-900 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            {actualizando
              ? "Actualizando…"
              : "↻ Actualizar"}
          </button>
        </div>
      </section>

      <div className="sticky top-[57px] z-20 -mx-3 mb-5 bg-gray-50/95 px-3 py-2 backdrop-blur sm:static sm:mx-0 sm:bg-transparent sm:px-0 sm:py-0 sm:backdrop-blur-0">
        <div className="grid grid-cols-5 gap-1 rounded-2xl border border-gray-200 bg-white p-1 shadow-sm sm:border-0 sm:bg-transparent sm:shadow-none">
          {[
            ["resumen", "Resumen"],
            ["calidad", "Calidad"],
            ["ejecutivos", "Ejecutivos"],
            ["cartera", "Cartera"],
            ["historico", "Histórico"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setVistaSupervisor(key)}
              className={`rounded-xl px-2 py-2.5 text-[11px] font-semibold transition-colors sm:px-4 sm:text-sm ${
                vistaSupervisor === key
                  ? "bg-esacom-lime-light text-esacom-ink"
                  : "text-gray-500 hover:text-esacom-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {vistaSupervisor === "resumen" && (
        <>
      <section className="mb-5 rounded-2xl border border-lime-200 bg-gradient-to-r from-lime-50 to-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-extrabold text-gray-900">Estado comercial de tu equipo</h2>
            <p className="mt-1 text-xs text-gray-600">Identifica rápidamente pendientes de instalación y casos comerciales por ejecutivo.</p>
          </div>
          <button type="button" onClick={() => setVistaSupervisor("cartera")} className="min-h-11 shrink-0 rounded-xl bg-lime-600 px-5 text-sm font-bold text-white shadow-sm hover:bg-lime-700">Revisar cartera →</button>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-white p-3 text-center"><strong className="block text-xl font-black text-green-800">{actividadEquipo?.instaladas ?? 0}</strong><span className="text-[10px] font-semibold text-gray-600">Instaladas</span></div>
          <div className="rounded-xl bg-white p-3 text-center"><strong className="block text-xl font-black text-orange-700">{casosPendientesInstalacion}</strong><span className="text-[10px] font-semibold text-gray-600">Pend. instalación</span></div>
          <div className="rounded-xl bg-white p-3 text-center"><strong className="block text-xl font-black text-blue-700">{casosPendientesComercial}</strong><span className="text-[10px] font-semibold text-gray-600">Pend. comercial</span></div>
        </div>
      </section>
      <section className="mb-7" id="vision-general">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">
            Qué requiere atención
          </h2>

          <p className="text-xs text-gray-500">
            Primero revisa los clientes que todavía pueden recuperar el pago y luego anticipa los próximos vencimientos.
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
              {rguGestionarAhora} RGU requieren atención prioritaria.
            </p>

            <p className="mt-2 text-[11px] text-gray-500">
              {venceHoyEquipo.clientes || 0} vencen hoy ·{" "}
              {gestionableEquipo.clientes || 0} están entre +1 y +8 días.
            </p>

            <a
              href="/accionables?estado=vencida_gestionable"
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-orange-600 px-3 text-xs font-bold text-white transition hover:bg-orange-700"
            >
              Ver gestión →
            </a>
          </div>

          {/* ANTICIPAR */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            Number(porVencerEquipo.clientes || 0) > 0
              ? "border-blue-200 bg-blue-50"
              : "border-gray-200 bg-white"
          }`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-blue-700">
              Anticipar pagos
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {porVencerEquipo.clientes || 0}
              <span className="ml-2 text-sm font-semibold text-gray-500">
                clientes
              </span>
            </p>

            <p className="mt-1 text-xs text-gray-600">
              {porVencerEquipo.rgu || 0} RGU todavía no vencen.
            </p>

            <p className="mt-2 text-[11px] text-gray-500">
              El equipo aún está a tiempo de anticipar estos pagos.
            </p>

            <a
              href="/accionables?estado=por_vencer"
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-blue-600 px-3 text-xs font-bold text-white transition hover:bg-blue-700"
            >
              Ver próximos →
            </a>
          </div>

          {/* KPI EQUIPO */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            tienePoblacionKpi(calidadActual) &&
            Number(calidadActual?.pct_cumplimiento || 0) >=
              Number(calidadActual?.meta_pct || 0)
              ? "border-green-200 bg-green-50"
              : "border-red-200 bg-red-50"
          }`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-green-700">
              KPI del equipo
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {tienePoblacionKpi(calidadActual)
                ? `${porcentajeEquipo}%`
                : "Sin medición"}
            </p>

            <p className="mt-1 text-xs text-gray-600">
              Meta {Number(calidadActual?.meta_pct || 0).toFixed(0)}% ·{" "}
              {ejecutivosBajoMeta} bajo meta.
            </p>

            <button
              type="button"
              onClick={() => setVistaSupervisor("calidad")}
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-gray-200 bg-white px-3 text-xs font-bold text-gray-700"
            >
              Ver Calidad →
            </button>
          </div>

          {/* FUERA DE PLAZO */}
          <div className={`rounded-2xl border p-4 shadow-sm ${
            Number(fueraPlazoEquipo.clientes || 0) > 0
              ? "border-red-200 bg-red-50"
              : "border-gray-200 bg-white"
          }`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-red-700">
              Fuera de plazo
            </p>

            <p className="mt-2 text-3xl font-black text-gray-900">
              {fueraPlazoEquipo.clientes || 0}
              <span className="ml-2 text-sm font-semibold text-gray-500">
                clientes
              </span>
            </p>

            <p className="mt-1 text-xs text-gray-600">
              {fueraPlazoEquipo.rgu || 0} RGU superaron los +8 días.
            </p>

            <p className="mt-2 text-[11px] text-gray-500">
              Se mantienen visibles para seguimiento y trazabilidad.
            </p>

            <a
              href="/accionables?estado=vencida"
              className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-red-200 bg-white px-3 text-xs font-bold text-red-700"
            >
              Ver casos →
            </a>
          </div>

        </div>

        <div className="mt-3 rounded-2xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-[11px] text-blue-800">
          <strong>Regla de gestión:</strong> primero recuperar clientes vencidos hasta +8 días y luego anticipar los próximos vencimientos.
        </div>
      </section>

      {prioridadEjecutivos.length > 0 && (
        <section className="mb-7">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-extrabold text-gray-900">
                Ejecutivos a priorizar
              </h2>

              <p className="text-xs text-gray-500">
                Ordenados automáticamente según los clientes que requieren gestión de pago.
              </p>
            </div>

            <a
              href="/accionables"
              className="text-xs font-bold text-blue-700 hover:underline"
            >
              Ver todos los accionables →
            </a>
          </div>

          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="hidden grid-cols-[minmax(220px,1.5fr)_0.7fr_0.7fr_0.7fr_auto] gap-3 border-b border-gray-100 bg-gray-50 px-4 py-3 text-[10px] font-bold uppercase tracking-wide text-gray-400 md:grid">
              <span>Ejecutivo</span>
              <span>Urgentes</span>
              <span>Por vencer</span>
              <span>RGU prioridad</span>
              <span></span>
            </div>

            <div className="divide-y divide-gray-100">
              {prioridadEjecutivos.slice(0, 8).map((fila, index) => (
                <div
                  key={fila.nombre}
                  className={`grid gap-3 px-4 py-3 md:grid-cols-[minmax(220px,1.5fr)_0.7fr_0.7fr_0.7fr_auto] md:items-center ${
                    index < 3 && fila.urgentes > 0
                      ? "bg-orange-50/40"
                      : "bg-white"
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      {index < 3 && fila.urgentes > 0 && (
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-orange-100 text-[10px] font-black text-orange-700">
                          {index + 1}
                        </span>
                      )}

                      <p className="text-xs font-extrabold text-gray-900">
                        {fila.nombre}
                      </p>
                    </div>

                    <p className="mt-1 text-[10px] text-gray-400 md:hidden">
                      Prioridad de gestión del período actual
                    </p>
                  </div>

                  <div>
                    <p className="text-[9px] font-bold uppercase text-gray-400 md:hidden">
                      Urgentes
                    </p>

                    <p
                      className={`text-sm font-black ${
                        fila.urgentes > 0
                          ? "text-orange-700"
                          : "text-gray-400"
                      }`}
                    >
                      {fila.urgentes}
                    </p>

                    <p className="text-[9px] text-gray-400">
                      {fila.rguUrgentes} RGU
                    </p>
                  </div>

                  <div>
                    <p className="text-[9px] font-bold uppercase text-gray-400 md:hidden">
                      Por vencer
                    </p>

                    <p className="text-sm font-black text-blue-700">
                      {fila.porVencer}
                    </p>

                    <p className="text-[9px] text-gray-400">
                      {fila.rguPorVencer} RGU
                    </p>
                  </div>

                  <div>
                    <p className="text-[9px] font-bold uppercase text-gray-400 md:hidden">
                      Total prioridad
                    </p>

                    <p className="text-sm font-black text-gray-900">
                      {fila.rguUrgentes + fila.rguPorVencer}
                    </p>

                    <p className="text-[9px] text-gray-400">
                      RGU
                    </p>
                  </div>

                  <a
                    href={`/accionables?ejecutivo=${encodeURIComponent(
                      fila.nombre
                    )}&estado=${
                      fila.gestionables > 0
                        ? "vencida_gestionable"
                        : fila.hoy > 0
                          ? "vence_hoy"
                          : fila.porVencer > 0
                            ? "por_vencer"
                            : "vencida"
                    }`}
                    className="inline-flex min-h-9 items-center justify-center rounded-xl border border-gray-200 bg-white px-3 text-[11px] font-bold text-gray-700 hover:bg-gray-50"
                  >
                    Ver gestión →
                  </a>
                </div>
              ))}
            </div>

            {prioridadEjecutivos.length > 8 && (
              <div className="border-t border-gray-100 bg-gray-50 px-4 py-3 text-center">
                <a
                  href="/accionables"
                  className="text-[11px] font-bold text-blue-700"
                >
                  Ver los {prioridadEjecutivos.length} ejecutivos con casos →
                </a>
              </div>
            )}
          </div>
        </section>
      )}

      <section className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">
            Mi equipo ·{" "}
            {nombreMes(mesActual)}
          </h2>

          <p className="text-xs text-gray-500">
            Producción del mes calendario: Fijo por RGU vendidos y Móvil por portadas efectivas vendidas en este período. ESACOM es la fuente oficial.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <TarjetaResumen
            titulo="RGU Fijo vendidos"
            valor={`${
              prodEquipo?.rgu_fijo_vendidos
              || 0
            } RGU`}
            detalle={`${
              prodEquipo?.ventas_fijo
              || 0
            } ventas · ${
              prodEquipo
                ?.rgu_fijo_gestionables
              || 0
            } RGU operativos · ${
              prodEquipo
                ?.rgu_fijo_anulados
              || 0
            } anulados`}
            tono="verde"
          />

          <TarjetaResumen
            titulo={`Portadas Móvil · ${nombreMes(mesActual)}`}
            valor={`${
              prodEquipo?.kpi_movil_portadas
              || 0
            } portadas`}
            detalle={`Del mes · Principal ${
              prodEquipo?.movil
                ?.principal || 0
            } · Adicional ${
              prodEquipo?.movil
                ?.adicional || 0
            }`}
            tono="lima"
          />

          <TarjetaResumen
            titulo="Actividad del equipo"
            valor={`${
              actividadEquipo?.total || 0
            } ventas`}
            detalle={`${
              actividadEquipo
                ?.instaladas || 0
            } instaladas · ${
              actividadEquipo
                ?.pendiente_instalacion
              || 0
            } pend. instalación`}
            tono="azul"
          />

          <TarjetaResumen
            titulo="Ejecutivos asignados"
            valor={
              resumen
                ?.ejecutivos_asignados
              ?? 0
            }
            detalle={`${
              resumen
                ?.ejecutivos_regulares
              ?? 0
            } Regular · ${
              resumen
                ?.ejecutivos_honorarios
              ?? 0
            } Honorarios`}
          />
        </div>
      </section>


      <section className="mb-7 rounded-2xl border border-blue-100 bg-blue-50/30 p-4 shadow-sm">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">Control operativo ESACOM · Hoy</h2>
          <p className="mt-1 text-xs text-gray-500">Fotografía vigente para comparar con el control diario de Gerencia. Incluye el equipo y, cuando corresponde, tu producción propia sin mezclarla con la producción del mes.</p>
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <TarjetaResumen titulo="Fijo completado" valor={`${Number(controlEquipo?.rgu_fijo_completados || 0) + Number(controlPropia?.rgu_fijo_completados || 0)} RGU`} detalle={`Equipo ${controlEquipo?.rgu_fijo_completados || 0} · Propia ${controlPropia?.rgu_fijo_completados || 0}`} tono="verde" />
          <TarjetaResumen titulo="Fijo pend. instalación" valor={`${Number(controlEquipo?.rgu_fijo_pendiente_instalacion || 0) + Number(controlPropia?.rgu_fijo_pendiente_instalacion || 0)} RGU`} detalle={`Equipo ${controlEquipo?.rgu_fijo_pendiente_instalacion || 0} · Propia ${controlPropia?.rgu_fijo_pendiente_instalacion || 0}`} tono="neutro" />
          <TarjetaResumen titulo="Móvil efectivo vigente" valor={`${Number(controlEquipo?.kpi_movil_portadas || 0) + Number(controlPropia?.kpi_movil_portadas || 0)} portadas`} detalle={`Equipo ${controlEquipo?.kpi_movil_portadas || 0} · Propia ${controlPropia?.kpi_movil_portadas || 0}`} tono="azul" />
          <TarjetaResumen titulo="Móvil por activar" valor={`${Number(controlEquipo?.movil_pendiente_activacion || 0) + Number(controlPropia?.movil_pendiente_activacion || 0)}`} detalle="Líneas vigentes todavía sin evidencia efectiva." />
        </div>
      </section>

      <section className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">
            Visual del equipo
          </h2>

          <p className="text-xs text-gray-500">
            Gráficos rápidos para detectar
            estado operativo y prioridades de
            Calidad sin recorrer toda la
            tabla.
          </p>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <EstadoVentasDonut
            actividad={actividadEquipo}
            titulo={`Estado de ventas · ${nombreMes(
              mesActual,
            )}`}
          />

                    <UrgenciaBarChart
            titulo={`Gestión de pago · ${
              accionablesEquipo?.camadas_abiertas?.[0]
                ? nombreMes(accionablesEquipo.camadas_abiertas[0])
                : "Sin período"
            }`}
            subtitulo="RGU del equipo según la ventana real de gestión de pago."
            items={[
              {
                name: "Vencida gestionable",
                value:
                  accionablesEquipo?.vencida_gestionable?.rgu || 0,
              },
              {
                name: "Vence hoy",
                value:
                  accionablesEquipo?.vence_hoy?.rgu || 0,
              },
              {
                name: "Por vencer",
                value:
                  accionablesEquipo?.por_vencer?.rgu || 0,
              },
              {
                name: "Fuera de plazo",
                value:
                  accionablesEquipo?.vencida?.rgu || 0,
              },
            ]}
          />
        </div>
      </section>
        </>
      )}

      {vistaSupervisor === "ejecutivos" && (
        <>
        <section className="mb-4 rounded-2xl border border-blue-100 bg-blue-50/50 px-4 py-3">
          <h2 className="text-sm font-extrabold text-blue-900">Ejecutivos del equipo</h2>
          <p className="mt-1 text-xs text-blue-800/80">Busca, compara y abre la cartera de un ejecutivo. Regular y Honorarios permanecen separados.</p>
        </section>
      {propiaDisponible && (
        <section className="mb-5 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-gray-500">Mi producción propia · {nombreMes(mesActual)}</p>
              <p className="mt-1 text-[11px] text-gray-400">Se muestra separada del equipo para no mezclar tus ventas con las de tus ejecutivos.</p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-xl bg-green-50 px-3 py-2 font-semibold text-green-800">{prodPropia?.rgu_fijo_vendidos || 0} RGU Fijo</span>
              <span className="rounded-xl bg-esacom-lime-light px-3 py-2 font-semibold text-esacom-ink">{prodPropia?.kpi_movil_portadas || 0} portadas Móvil del mes</span>
            </div>
          </div>
        </section>
      )}
        </>
      )}

      {vistaSupervisor === "calidad" && (
        <>
      <section id="calidad-equipo" className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">
            Calidad del equipo
          </h2>

          <p className="text-xs text-gray-500">
            Se muestra el último período de
            Calidad actualmente medido por
            Claro.
          </p>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
          <CalidadEquipo
            corte={calidadActual}
            ultimaCarga={ultimaCarga}
          />

          <TendenciaKpiChart
            corte={calidadActual}
          />
        </div>
      </section>

      <section className="mb-7">
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">Períodos de Calidad en curso</h2>
          <p className="text-xs text-gray-500">Septiembre, Agosto y cualquier camada abierta permanecen aquí hasta recibir un CIERRE oficial de Claro.</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {(kpiEquipo || []).map((corte) => (
            <TarjetaHistorico
              key={`abierto-${corte.mes_ano}`}
              corte={corte}
              cerrado={false}
            />
          ))}
        </div>
        {(kpiEquipo || []).length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
            No hay períodos de Calidad en curso para este equipo.
          </div>
        )}
      </section>
        </>
      )}

      {/* HISTÓRICO KPI DEL SUPERVISOR */}
      {vistaSupervisor === "historico" && (
      <section
        id="historico"
        className="mb-7"
      >
        <div className="mb-3">
          <h2 className="text-base font-extrabold text-gray-900">
            Histórico KPI del equipo
          </h2>

          <p className="text-xs text-gray-500">
            Aquí aparecen únicamente meses con CIERRE OFICIAL de Claro. Estos resultados permanecen congelados y no cambian con nuevas sincronizaciones ESACOM.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {(historicoKpi || []).map(
            (corte) => (
              <TarjetaHistorico
                key={`cerrado-${
                  corte.mes_ano
                }`}
                corte={corte}
                cerrado
              />
            ),
          )}
        </div>

        {(historicoKpi || []).length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
            Todavía no hay cierres oficiales disponibles para este equipo.
          </div>
        )}
      </section>
      )}

      {vistaSupervisor === "ejecutivos" && (
        <>
      <section className="mb-7">
        <RankingKpiBarChart
          filas={ranking.filter((fila) => tienePoblacionKpi(corteActual(fila)))}
          obtenerCorte={corteActual}
          limite={8}
        />
      </section>


      <section id="seguimiento-equipo" className="mb-7 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-gray-100 p-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              Seguimiento de ejecutivos ·
              Calidad actual
            </h2>

            <p className="mt-1 text-xs text-gray-400">
              {resumen
                ?.ejecutivos_regulares
              ?? 0}{" "}
              ejecutivos Regular asignados.
              Honorarios se mantiene separado.
            </p>
          </div>

          <input
            value={busquedaEjecutivo}
            onChange={(e) =>
              setBusquedaEjecutivo(
                e.target.value,
              )
            }
            placeholder="Buscar ejecutivo por nombre o RUT..."
            className="min-h-11 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-esacom-red/20 md:w-80"
          />
        </div>


        <div className="divide-y divide-gray-100 md:hidden">
          {ranking.map((fila) => {
            const e =
              fila.ejecutivo;

            const c =
              corteActual(fila);

            const medido = tienePoblacionKpi(c);

            const cumple =
              medido
              && Number(
                c.pct_cumplimiento
                || 0,
              )
                >= Number(
                  c.meta_pct || 0,
                );

            return (
              <div
                key={`mobile-${e.id}`}
                className="p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {e.nombre}
                    </p>

                    <p className="text-xs text-gray-400">
                      {e.rut}
                    </p>
                  </div>

                  <div className="text-right">
                    <p
                      className={`text-xl font-bold ${claseKpi(
                        c,
                      )}`}
                    >
                      {medido
                        ? `${Number(
                            c.pct_cumplimiento
                            || 0,
                          ).toFixed(
                            2,
                          )}%`
                        : "Sin medición"}
                    </p>

                    <p className="text-[10px] text-gray-400">
                      Meta{" "}
                      {medido
                        ? `${Number(
                            c.meta_pct
                            || 0,
                          ).toFixed(
                            0,
                          )}%`
                        : "—"}
                    </p>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-4 gap-2 text-center text-[10px]">
                  <div className="rounded-lg bg-green-50 p-2">
                    <strong className="block text-sm text-green-800">
                      {c?.pagadas || 0}
                    </strong>
                    Pago
                  </div>

                  <div className="rounded-lg bg-blue-50 p-2">
                    <strong className="block text-sm text-blue-800">
                      {c?.pendientes || 0}
                    </strong>
                    Pendiente
                  </div>

                  <div className="rounded-lg bg-red-50 p-2">
                    <strong className="block text-sm text-red-800">
                      {c?.no_pago || 0}
                    </strong>
                    No pago
                  </div>

                  <div className="rounded-lg bg-gray-50 p-2">
                    <strong className="block text-sm text-gray-900">
                      {medido
                        ? c?.faltan_para_meta || 0
                        : "—"}
                    </strong>
                    Faltan a meta
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <span
                    className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                      !medido
                        ? "bg-gray-100 text-gray-500"
                        : cumple
                          ? "bg-green-50 text-green-700"
                          : "bg-red-50 text-red-700"
                    }`}
                  >
                    {!medido
                      ? "Sin medición"
                      : cumple
                        ? "Cumple"
                        : "Aún no cumple"}
                  </span>

                  <button
                    onClick={() => abrirCarteraEjecutivo(e.id)}
                    className="min-h-10 rounded-xl bg-esacom-red-light px-3 text-xs font-semibold text-esacom-red"
                  >
                    Ver cartera
                  </button>
                </div>
              </div>
            );
          })}
        </div>


        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1050px] text-xs">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="px-4 py-3 text-left">
                  Ejecutivo
                </th>

                <th className="px-3 py-3 text-center">
                  KPI actual
                </th>

                <th className="px-3 py-3 text-center">
                  Meta
                </th>

                <th className="px-3 py-3 text-center">
                  Estado
                </th>

                <th className="px-3 py-3 text-right">
                  Pago
                </th>

                <th className="px-3 py-3 text-right">
                  Pendiente
                </th>

                <th className="px-3 py-3 text-right">
                  No pago
                </th>

                <th className="px-3 py-3 text-right">
                  Faltan a meta
                </th>

                <th className="px-4 py-3" />
              </tr>
            </thead>

            <tbody>
              {ranking.map((fila) => {
                const e =
                  fila.ejecutivo;

                const c =
                  corteActual(fila);

                const medido = tienePoblacionKpi(c);

                const cumple =
                  medido
                  && Number(
                    c.pct_cumplimiento
                    || 0,
                  )
                    >= Number(
                      c.meta_pct || 0,
                    );

                return (
                  <tr
                    key={e.id}
                    className="border-t border-gray-100 hover:bg-gray-50/60"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-800">
                        {e.nombre}
                      </p>

                      <p className="text-[10px] text-gray-400">
                        {e.rut} ·{" "}
                        {e.equipo
                          || "Sin equipo"}
                      </p>
                    </td>

                    <td
                      className={`px-3 py-3 text-center font-bold ${claseKpi(
                        c,
                      )}`}
                    >
                      {medido
                        ? `${Number(
                            c.pct_cumplimiento
                            || 0,
                          ).toFixed(
                            2,
                          )}%`
                        : "Sin medición"}
                    </td>

                    <td className="px-3 py-3 text-center">
                      {medido
                        ? `${Number(
                            c.meta_pct
                            || 0,
                          ).toFixed(
                            0,
                          )}%`
                        : "—"}
                    </td>

                    <td className="px-3 py-3 text-center">
                      <span
                        className={`rounded-full px-2 py-1 text-[10px] font-bold ${
                          !medido
                            ? "bg-gray-100 text-gray-500"
                            : cumple
                              ? "bg-green-50 text-green-700"
                              : "bg-red-50 text-red-700"
                        }`}
                      >
                        {!medido
                          ? "Sin medición"
                          : cumple
                            ? "Cumple"
                            : "No cumple"}
                      </span>
                    </td>

                    <td className="px-3 py-3 text-right font-semibold text-green-700">
                      {c?.pagadas || 0}
                    </td>

                    <td className="px-3 py-3 text-right font-semibold text-blue-700">
                      {c?.pendientes || 0}
                    </td>

                    <td className="px-3 py-3 text-right font-semibold text-red-700">
                      {c?.no_pago || 0}
                    </td>

                    <td className="px-3 py-3 text-right font-semibold text-esacom-red">
                      {medido
                        ? `${c?.faltan_para_meta || 0} RGU`
                        : "—"}
                    </td>

                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => abrirCarteraEjecutivo(e.id)}
                        className="text-[11px] font-semibold text-esacom-red hover:underline"
                      >
                        Ver cartera
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {ranking.length === 0 && (
          <p className="p-6 text-center text-sm text-gray-400">
            No hay KPI actual atribuido a
            ejecutivos del equipo.
          </p>
        )}
      </section>


      <section className="mb-7 overflow-hidden rounded-2xl border border-amber-200 bg-white shadow-sm">
        <div className="flex flex-col gap-2 border-b border-amber-100 bg-amber-50/50 p-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">
              Seguimiento Honorarios · Calidad
              actual
            </h2>

            <p className="mt-1 text-xs text-amber-800">
              Se muestra el KPI real de pago y
              la producción ESACOM del mes.
              Honorarios no participa en la
              meta, promedio ni ranking Regular.
            </p>
          </div>

          <span className="text-[11px] font-semibold text-amber-700">
            Meta Honorarios: pendiente de
            definición
          </span>
        </div>


        <div className="divide-y divide-gray-100 md:hidden">
          {honorariosFiltrados.map(
            (fila) => {
              const e =
                fila.ejecutivo || {};

              const c =
                fila.calidad_actual;

              const p =
                fila.produccion_mes_actual
                || {};

              return (
                <div
                  key={`hon-mobile-${e.id}`}
                  className="p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {e.nombre}
                      </p>

                      <p className="text-xs text-gray-400">
                        {e.rut}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-xl font-bold text-blue-700">
                        {c?.tiene_datos
                          ? `${Number(
                              c.pct_cumplimiento
                              || 0,
                            ).toFixed(
                              2,
                            )}%`
                          : "Sin medición"}
                      </p>

                      <p className="text-[10px] text-gray-400">
                        KPI de pago
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-4 gap-2 text-center text-[10px]">
                    <div className="rounded-lg bg-green-50 p-2">
                      <strong className="block text-sm text-green-800">
                        {p
                          ?.ventas_fijo
                          || 0}
                      </strong>
                      Ventas mes
                    </div>

                    <div className="rounded-lg bg-gray-50 p-2">
                      <strong className="block text-sm text-gray-900">
                        {p
                          ?.rgu_fijo_vendidos
                          || 0}
                      </strong>
                      RGU mes
                    </div>

                    <div className="rounded-lg bg-green-50 p-2">
                      <strong className="block text-sm text-green-800">
                        {c?.pagadas || 0}
                      </strong>
                      Pago
                    </div>

                    <div className="rounded-lg bg-gray-50 p-2">
                      <strong className="block text-sm text-gray-900">
                        {c?.total || 0}
                      </strong>
                      Total KPI
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between">
                    <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700">
                      Sin meta aplicada
                    </span>

                    <button
                      onClick={() => abrirCarteraEjecutivo(e.id)}
                      className="min-h-10 rounded-xl bg-amber-50 px-3 text-xs font-semibold text-amber-800"
                    >
                      Ver cartera
                    </button>
                  </div>
                </div>
              );
            },
          )}
        </div>


        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1050px] text-xs">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="px-4 py-3 text-left">
                  Ejecutivo Honorarios
                </th>

                <th className="px-3 py-3 text-center">
                  Ventas{" "}
                  {nombreMes(
                    mesActual,
                  )}
                </th>

                <th className="px-3 py-3 text-center">
                  RGU{" "}
                  {nombreMes(
                    mesActual,
                  )}
                </th>

                <th className="px-3 py-3 text-center">
                  KPI pago actual
                </th>

                <th className="px-3 py-3 text-right">
                  Pago
                </th>

                <th className="px-3 py-3 text-right">
                  Pendiente
                </th>

                <th className="px-3 py-3 text-right">
                  No pago
                </th>

                <th className="px-3 py-3 text-right">
                  Fuera plazo
                </th>

                <th className="px-3 py-3 text-right">
                  Total RGU KPI
                </th>

                <th className="px-4 py-3" />
              </tr>
            </thead>

            <tbody>
              {honorariosFiltrados.map(
                (fila) => {
                  const e =
                    fila.ejecutivo
                    || {};

                  const c =
                    fila.calidad_actual;

                  const p =
                    fila
                      .produccion_mes_actual
                    || {};

                  return (
                    <tr
                      key={`hon-${e.id}`}
                      className="border-t border-gray-100 hover:bg-amber-50/30"
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-800">
                          {e.nombre}
                        </p>

                        <p className="text-[10px] text-gray-400">
                          {e.rut} ·
                          Honorarios
                        </p>
                      </td>

                      <td className="px-3 py-3 text-center font-semibold text-gray-800">
                        {p
                          ?.ventas_fijo
                          || 0}
                      </td>

                      <td className="px-3 py-3 text-center font-semibold text-gray-800">
                        {p
                          ?.rgu_fijo_vendidos
                          || 0}
                      </td>

                      <td className="px-3 py-3 text-center font-bold text-blue-700">
                        {c?.tiene_datos
                          ? `${Number(
                              c.pct_cumplimiento
                              || 0,
                            ).toFixed(
                              2,
                            )}%`
                          : "—"}
                      </td>

                      <td className="px-3 py-3 text-right font-semibold text-green-700">
                        {c?.pagadas || 0}
                      </td>

                      <td className="px-3 py-3 text-right font-semibold text-blue-700">
                        {c
                          ?.pendientes
                          || 0}
                      </td>

                      <td className="px-3 py-3 text-right font-semibold text-red-700">
                        {c?.no_pago || 0}
                      </td>

                      <td className="px-3 py-3 text-right font-semibold text-orange-700">
                        {c
                          ?.fuera_plazo
                          || 0}
                      </td>

                      <td className="px-3 py-3 text-right font-semibold text-gray-800">
                        {c?.total || 0}
                      </td>

                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => abrirCarteraEjecutivo(e.id)}
                          className="text-[11px] font-semibold text-amber-700 hover:underline"
                        >
                          Ver cartera
                        </button>
                      </td>
                    </tr>
                  );
                },
              )}
            </tbody>
          </table>
        </div>

        {honorariosFiltrados.length === 0 && (
          <p className="p-6 text-center text-sm text-gray-400">
            No hay ejecutivos Honorarios activos
            asignados o no coinciden con la
            búsqueda.
          </p>
        )}
      </section>


        </>
      )}

      {vistaSupervisor === "cartera" && (
      <section id="cartera-equipo">
        <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50/50 px-4 py-3">
          <h2 className="text-sm font-extrabold text-blue-900">Cartera del equipo</h2>
          <p className="mt-1 text-xs text-blue-800/80">Filtra clientes por ejecutivo, perfil y estado sin mezclarlo con el seguimiento KPI.</p>
        </div>
        <div className="mb-4">
          <h3 className="mb-2 text-sm font-extrabold text-gray-900">Estado comercial del equipo</h3>
          <p className="mb-3 text-xs text-gray-500">Toca un estado para filtrar la cartera. «Del período» y los estados de instalación no representan categorías adicionales que deban sumarse.</p>
          <TarjetasEstadoComercial
            activo={estado || "TODOS"}
            onSeleccionar={(key) => setEstado(key === "TODOS" ? "" : key)}
            items={[
              { key: "TODOS", label: "Toda la cartera", valor: conteosEstadoComercial.TODOS, detalle: "En la selección actual", tono: "lima", icono: "☷" },
              { key: "NUEVOS", label: "Del período", valor: conteosEstadoComercial.NUEVOS, detalle: "Ventas vigentes, sin anulados", tono: "verde", icono: "＋" },
              { key: "INSTALADO", label: "Instalados", valor: conteosEstadoComercial.INSTALADO, detalle: "Servicio completado", tono: "verde", icono: "✓" },
              { key: "PENDIENTE_INSTALACION", label: "Pend. instalación", valor: conteosEstadoComercial.PENDIENTE_INSTALACION, detalle: "En coordinación", tono: "naranja", icono: "⌛" },
              { key: "PENDIENTE_COMERCIAL", label: "Pend. comercial", valor: conteosEstadoComercial.PENDIENTE_COMERCIAL, detalle: "Requieren gestión", tono: "azul", icono: "◎" },
              { key: "ANULADO", label: "Anulados", valor: conteosEstadoComercial.ANULADO, detalle: "Ventas anuladas", tono: "rojo", icono: "✕" },
            ]}
          />
        </div>
        <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-base font-extrabold text-gray-900">
              Clientes y ventas ({ventasFiltradas.length})
            </h3>

            <p className="text-xs text-gray-500">
              Por defecto muestra{" "}
              {nombreMes(mesActual)}. Fuente
              oficial ESACOM.
            </p>
          </div>

          {snapshotEjecutivos && (
            <span className="text-[11px] text-gray-400">
              Corte Calidad{" "}
              {snapshotEjecutivos
                .fecha_corte || "—"}
            </span>
          )}
        </div>


        {ejecutivoFiltro && (
          <div className="mb-3 flex flex-col gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-800 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Ejecutivo:{" "}
              <strong>
                {ejecutivoSeleccionado
                  ?.ejecutivo?.nombre
                  || "seleccionado"}
              </strong>
            </span>

            <button
              onClick={() =>
                setEjecutivoFiltro("")
              }
              className="min-h-9 rounded-lg bg-white/70 px-3 font-semibold"
            >
              Ver todo el equipo
            </button>
          </div>
        )}


        <div className="mb-4 flex flex-col gap-3 md:flex-row">
          <input
            type="text"
            placeholder="Buscar cliente, RUT, pedido o ejecutivo..."
            value={busqueda}
            onChange={(e) =>
              setBusqueda(
                e.target.value,
              )
            }
            className="min-h-11 flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-esacom-red/20"
          />

          <select
            value={periodoCartera}
            onChange={(e) =>
              setPeriodoCartera(
                e.target.value,
              )
            }
            className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            <option value="MES_ACTUAL">
              Mes actual
            </option>

            <option value="TODAS">
              Toda la cartera
            </option>
          </select>

          <select
            value={perfilKpi}
            onChange={(e) =>
              setPerfilKpi(
                e.target.value,
              )
            }
            className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">
              Regular + Honorarios
            </option>

            <option value="REGULAR">
              Solo Regular
            </option>

            <option value="HONORARIOS">
              Solo Honorarios
            </option>
          </select>

          <label className="flex flex-col gap-1 text-[11px] font-semibold text-gray-600">
            Ordenar clientes
            <select aria-label="Ordenar cartera" value={ordenCartera} onChange={(e) => setOrdenCartera(e.target.value)} className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm">
              <option value="FECHA">Venta más reciente</option>
              <option value="NOMBRE">Nombre</option>
              <option value="ESTADO">Estado comercial</option>
            </select>
          </label>

          <select
            aria-label="Filtrar estado comercial"
            value={estado}
            onChange={(e) =>
              setEstado(
                e.target.value,
              )
            }
            className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            <option value="NUEVOS">Ventas vigentes del período</option>
            {ESTADOS.map((e) => (
              <option
                key={e.value}
                value={e.value}
              >
                {e.label}
              </option>
            ))}
          </select>
        </div>


        {ventas === null && (
          <div className="h-64 animate-pulse rounded-xl bg-gray-100" />
        )}

        {ventas
          && ventasFiltradas.length
            === 0 && (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-400">
            No hay clientes que coincidan con
            los filtros.
          </div>
        )}

        {ventas
          && ventasFiltradas.length
            > 0 && (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {ventasFiltradas.map(
              (v) => (
                <button
                  type="button"
                  onClick={() =>
                    setVentaDetalle(
                      v.id,
                    )
                  }
                  key={v.id}
                  className="w-full rounded-2xl border border-gray-200 border-l-4 border-l-lime-400 bg-white p-4 text-left shadow-sm transition hover:border-l-lime-500 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-lime-600 active:scale-[0.998]"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {v.nombre_cliente
                          || v.rut_cliente}
                      </p>

                      <p className="text-xs text-gray-400">
                        {v.rut_cliente}
                        {" · "}
                        {v.n_pedido}
                      </p>
                    </div>

                    <span
                      className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                        ESTADO_BADGE[
                          v
                            .estado_instalacion
                        ]
                        || "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {ESTADOS.find(
                        (e) =>
                          e.value
                          === v
                            .estado_instalacion,
                      )?.label
                        || v
                          .estado_instalacion}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <p className="text-xs font-medium text-blue-600">
                      {v.ejecutivo
                        ?.nombre
                        || "Sin ejecutivo"}
                    </p>

                    {v.ejecutivo && (
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                          v.ejecutivo
                            .tipo_kpi
                            === "HONORARIOS"
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-gray-200 bg-gray-50 text-gray-500"
                        }`}
                      >
                        {v.ejecutivo
                          .tipo_kpi
                          === "HONORARIOS"
                          ? "HONORARIOS"
                          : "REGULAR"}
                      </span>
                    )}
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                    <div>
                      <p className="text-gray-400">
                        Producto
                      </p>

                      <p>
                        {v.promocion
                          ?.nombre
                          || "—"}
                      </p>
                    </div>

                    <div>
                      <p className="text-gray-400">
                        F. venta
                      </p>

                      <p>
                        {v.fecha_venta
                          || "—"}
                      </p>
                    </div>

                    <div>
                      <p className="text-gray-400">
                        1ª agenda
                      </p>

                      <p>
                        {v.primera_agenda
                          || "—"}
                      </p>
                    </div>

                    <div>
                      <p className="text-gray-400">
                        F. cierre
                      </p>

                      <p>
                        {v.fecha_cierre
                          || "—"}
                      </p>
                    </div>
                  </div>
                  <span className="mt-3 flex min-h-10 items-center justify-center rounded-xl border border-lime-200 bg-lime-50 text-xs font-extrabold text-lime-900 md:ml-auto md:w-fit md:px-4">
                    Ver cliente y seguimiento →
                  </span>
                </button>
              ),
            )}
          </div>
        )}
      </section>
      )}

      <ClienteDetalleModal
        ventaId={ventaDetalle}
        onClose={() =>
          setVentaDetalle(null)
        }
      />
    </Layout>
  );
}