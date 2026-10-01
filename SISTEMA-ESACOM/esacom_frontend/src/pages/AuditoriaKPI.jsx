import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
import { ADMIN_URL } from "../api/client";
import {
  fetchHistorialCargas,
  fetchRegistrosKPI,
  fetchResumenAuditoriaKPI,
} from "../api/apelaciones";

const FILTROS = [
  ["alertas", "Todas las alertas"],
  ["sin_cruce", "Sin venta ESACOM"],
  ["rut", "RUT distinto"],
  ["rgu", "RGU distinto"],
  ["propietario", "Propietario / CE distinto"],
  ["estado", "Estado Claro ≠ ESACOM"],
  ["fuera_medicion", "Fuera de medición"],
  ["ejecutivo", "Ejecutivo no resuelto"],
  ["todos", "Todos los registros"],
];

function paramsFiltro(tipo) {
  switch (tipo) {
    case "sin_cruce": return { cruce_ok: false };
    case "rut": return { diferencia_rut: true };
    case "rgu": return { diferencia_rgu: true };
    case "propietario": return { diferencia_propietario: true };
    case "estado": return { diferencia_estado: true };
    case "fuera_medicion": return { es_medible: false };
    case "ejecutivo": return { ejecutivo_kpi_no_resuelto: true };
    case "todos": return {};
    default: return { alerta: true };
  }
}

function alertas(registro) {
  const items = [];
  if (!registro.cruce_ok) items.push(["Sin venta", "bg-orange-50 text-orange-700"]);
  if (registro.diferencia_rut) items.push(["RUT", "bg-red-50 text-red-700"]);
  if (registro.diferencia_rgu) items.push(["RGU", "bg-red-50 text-red-700"]);
  if (registro.diferencia_propietario) items.push(["Propietario/CE", "bg-red-50 text-red-700"]);
  if (registro.diferencia_estado) items.push(["Estado", "bg-purple-50 text-purple-700"]);
  if (!registro.es_medible) items.push(["Fuera medición", "bg-gray-100 text-gray-600"]);
  if (registro.ejecutivo_kpi_no_resuelto) items.push(["Ejecutivo", "bg-red-50 text-red-700"]);
  return items;
}

function CeldaComparacion({ fuente, esacom, diferencia }) {
  return (
    <div className={`rounded-md px-2 py-1 ${diferencia ? "bg-red-50" : ""}`}>
      <div className="text-gray-800">{fuente || "—"}</div>
      <div className="text-[10px] text-gray-400">ESACOM: {esacom || "—"}</div>
    </div>
  );
}

export default function AuditoriaKPI() {
  const { user } = useAuth();
  const [cargas, setCargas] = useState(null);
  const [cargaId, setCargaId] = useState("");
  const [registros, setRegistros] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [filtro, setFiltro] = useState("alertas");
  const [busqueda, setBusqueda] = useState("");
  const [busquedaAplicada, setBusquedaAplicada] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchHistorialCargas({ tipo_base: "REPORTE_KPI", page_size: 100 })
      .then((data) => {
        setCargas(data);
        if (data.length > 0) setCargaId(String(data[0].id));
      })
      .catch(() => setError("No se pudo cargar el historial KPI."));
  }, []);

  useEffect(() => {
    if (!cargaId) return;
    setResumen(null);
    fetchResumenAuditoriaKPI({ carga: cargaId })
      .then(setResumen)
      .catch(() => setError("No se pudo calcular el resumen de auditoría."));
  }, [cargaId]);

  useEffect(() => {
    if (!cargaId) return;
    setCargando(true);
    setError("");
    const params = {
      carga: cargaId,
      ordering: "num_pedido",
      page: pagina,
      page_size: 100,
      ...paramsFiltro(filtro),
    };
    if (busquedaAplicada) params.search = busquedaAplicada;

    fetchRegistrosKPI(params)
      .then((data) => {
        setRegistros(data.results ?? data);
        setTotal(data.count ?? (data.results ?? data).length);
      })
      .catch(() => setError("No se pudo cargar la auditoría de este KPI."))
      .finally(() => setCargando(false));
  }, [cargaId, filtro, pagina, busquedaAplicada]);

  const carga = useMemo(
    () => (cargas || []).find((c) => String(c.id) === String(cargaId)),
    [cargas, cargaId]
  );

  const paginas = Math.max(1, Math.ceil(total / 100));

  function cambiarFiltro(value) {
    setFiltro(value);
    setPagina(1);
  }

  function buscar(e) {
    e.preventDefault();
    setPagina(1);
    setBusquedaAplicada(busqueda.trim());
  }

  return (
    <Layout
      titulo="Auditoría KPI"
      items={menuPorUsuario(user)}
    >
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_1fr] gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Carga KPI</label>
            <select
              value={cargaId}
              onChange={(e) => { setCargaId(e.target.value); setPagina(1); }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
            >
              {(cargas || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {new Date(c.creado_en).toLocaleString("es-CL")} · {c.archivo_nombre}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Mostrar</label>
            <select
              value={filtro}
              onChange={(e) => cambiarFiltro(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
            >
              {FILTROS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <form onSubmit={buscar}>
            <label className="block text-xs text-gray-500 mb-1">Pedido, RUT, propietario o Bill No.</label>
            <div className="flex gap-2">
              <input
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                placeholder="Buscar..."
              />
              <button className="rounded-lg bg-gray-900 text-white px-3 text-xs font-medium">Buscar</button>
            </div>
          </form>
        </div>
        {carga && (
          <div className="mt-3 text-xs text-gray-500 flex flex-wrap gap-x-5 gap-y-1">
            <span>Corte Claro: <strong>{carga.fecha_corte || "—"}</strong> · {carga.dia_reporte || "—"}</span>
            <span>Archivo: <strong>{carga.archivo_nombre}</strong></span>
            {(carga.avance_b1 || carga.avance_b2 || carga.avance_b3) && (
              <span>Avance correo: B1 {carga.avance_b1 ?? "—"}% · B2 {carga.avance_b2 ?? "—"}% · B3 {carga.avance_b3 ?? "—"}%</span>
            )}
          </div>
        )}
      </div>

      {resumen && (
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2 mb-5">
          {[
            ["Filas", resumen.total, "text-gray-900"],
            ["Cruzados", resumen.cruzados, "text-green-700"],
            ["Sin cruce", resumen.sin_cruce, "text-orange-600"],
            ["Inconsistencias", resumen.filas_con_inconsistencia, "text-red-600"],
            ["RUT", resumen.diferencia_rut, resumen.diferencia_rut ? "text-red-600" : "text-green-700"],
            ["RGU", resumen.diferencia_rgu, "text-red-600"],
            ["Prop./CE", resumen.diferencia_propietario, "text-red-600"],
            ["Fuera medición", resumen.fuera_medicion, "text-gray-600"],
          ].map(([label, value, color]) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-3">
              <p className="text-[11px] text-gray-400">{label}</p>
              <p className={`text-xl font-semibold ${color}`}>{Number(value || 0).toLocaleString("es-CL")}</p>
            </div>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3 mb-4">{error}</p>}
      {cargas?.length === 0 && (
        <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
          Aún no hay reportes KPI cargados.
        </div>
      )}
      {cargando && <div className="h-40 rounded-xl bg-gray-100 animate-pulse" />}

      {!cargando && cargaId && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[1200px]">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-gray-500">
                  <th className="text-left px-3 py-2 font-medium">Pedido / corte</th>
                  <th className="text-left px-3 py-2 font-medium">RUT Claro / ESACOM</th>
                  <th className="text-left px-3 py-2 font-medium">RGU Claro / ESACOM</th>
                  <th className="text-left px-3 py-2 font-medium">Propietario / CE</th>
                  <th className="text-left px-3 py-2 font-medium">Estado Claro</th>
                  <th className="text-left px-3 py-2 font-medium">Validación ESACOM</th>
                  <th className="text-left px-3 py-2 font-medium">Fechas</th>
                  <th className="text-left px-3 py-2 font-medium">Alertas</th>
                </tr>
              </thead>
              <tbody>
                {registros.map((r) => (
                  <tr key={r.id} className="border-b border-gray-100 last:border-0 align-top">
                    <td className="px-3 py-2">
                      <p className="font-medium text-gray-900">{r.num_pedido}</p>
                      <p className="text-gray-400">{r.camada} · {r.boleta} · {r.bill_no || "sin Bill"}</p>
                    </td>
                    <td className="px-3 py-2">
                      <CeldaComparacion fuente={r.rut_cliente} esacom={r.rut_esacom} diferencia={r.diferencia_rut} />
                    </td>
                    <td className="px-3 py-2">
                      <CeldaComparacion fuente={r.rgu ?? "—"} esacom={r.rgu_esacom ?? "—"} diferencia={r.diferencia_rgu} />
                    </td>
                    <td className="px-3 py-2">
                      <CeldaComparacion
                        fuente={r.propietario_final}
                        esacom={r.codigo_ce_esacom}
                        diferencia={r.diferencia_propietario}
                      />
                      {r.ejecutivo_esacom?.nombre && <p className="text-[10px] text-gray-400 mt-1">{r.ejecutivo_esacom.nombre}</p>}
                    </td>
                    <td className="px-3 py-2 text-gray-700">{r.kpi_texto || r.estado_normalizado || "—"}</td>
                    <td className="px-3 py-2">
                      <span className={r.diferencia_estado ? "text-red-700 font-medium" : "text-gray-700"}>
                        {r.estado_calculado || "—"}
                      </span>
                      {!r.es_medible && <p className="text-[10px] text-gray-400">No entra al denominador</p>}
                    </td>
                    <td className="px-3 py-2 text-gray-500 whitespace-nowrap">
                      <div>Vence: {r.fecha_vencimiento || "—"}</div>
                      <div>Límite: {r.fecha_limite_medicion || "—"}</div>
                      <div>Pago: {r.fecha_pago || "—"}</div>
                    </td>
                    <td className="px-3 py-2 max-w-xs">
                      <div className="flex flex-wrap gap-1">
                        {alertas(r).map(([a, estilo]) => (
                          <span key={a} className={`rounded-full px-2 py-0.5 ${estilo}`}>{a}</span>
                        ))}
                        {alertas(r).length === 0 && <span className="text-green-700">✓ Sin diferencias</span>}
                      </div>
                    </td>
                  </tr>
                ))}
                {registros.length === 0 && (
                  <tr><td colSpan="8" className="px-4 py-10 text-center text-gray-400">No hay registros para este filtro.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3 text-xs">
            <span className="text-gray-500">{total.toLocaleString("es-CL")} registros · página {pagina} de {paginas}</span>
            <div className="flex gap-2">
              <button
                disabled={pagina <= 1}
                onClick={() => setPagina((p) => Math.max(1, p - 1))}
                className="border rounded-md px-3 py-1.5 disabled:opacity-40"
              >← Anterior</button>
              <button
                disabled={pagina >= paginas}
                onClick={() => setPagina((p) => Math.min(paginas, p + 1))}
                className="border rounded-md px-3 py-1.5 disabled:opacity-40"
              >Siguiente →</button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
