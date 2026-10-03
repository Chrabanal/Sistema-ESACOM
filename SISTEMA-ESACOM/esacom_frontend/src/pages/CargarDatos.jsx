import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
import { ADMIN_URL } from "../api/client";
import { cargarExcel, fetchHistorialCargas } from "../api/apelaciones";

const TIPOS = [
  { value: "BASE_MATRIZ", label: "Base matriz (ventas, dotación, comunas, promociones)" },
  { value: "REPORTE_KPI", label: "KPI Calidad Claro · avance o cierre" },
];

export default function CargarDatos() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tipo, setTipo] = useState("BASE_MATRIZ");
  const [archivo, setArchivo] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [historial, setHistorial] = useState(null);
  const [fechaCorte, setFechaCorte] = useState("");
  const [diaReporte, setDiaReporte] = useState("MIERCOLES");
  const [formatoKpi, setFormatoKpi] = useState("DETALLADO");
  const [avanceB1, setAvanceB1] = useState("");
  const [avanceB2, setAvanceB2] = useState("");
  const [avanceB3, setAvanceB3] = useState("");
  const [metaB1, setMetaB1] = useState("");
  const [metaB2, setMetaB2] = useState("");
  const [metaB3, setMetaB3] = useState("");
  const inputRef = useRef(null);

  function cargarHistorial() {
    fetchHistorialCargas().then(setHistorial).catch(() => {});
  }

  useEffect(cargarHistorial, []);

  function handleDrop(e) {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setArchivo(f);
  }

  async function handleSubir() {
    if (!archivo) return;
    setSubiendo(true);
    setError("");
    setResultado(null);
    try {
      if (tipo === "REPORTE_KPI" && !fechaCorte) {
        setError("Indica la fecha de corte informada por Claro antes de cargar el KPI.");
        setSubiendo(false);
        return;
      }
      const metadata = tipo === "REPORTE_KPI"
        ? {
            fecha_corte: fechaCorte,
            dia_reporte: diaReporte,
            estado_reporte: ["DETALLADO", "AVANCE_MOVIL"].includes(formatoKpi) ? "AVANCE" : "CIERRE",
            formato_kpi: formatoKpi,
            avance_b1: avanceB1,
            avance_b2: avanceB2,
            avance_b3: avanceB3,
            meta_b1: metaB1,
            meta_b2: metaB2,
            meta_b3: metaB3,
          }
        : {};
      const data = await cargarExcel(archivo, tipo, metadata);
      setResultado(data.resumen);
      setArchivo(null);
      if (inputRef.current) inputRef.current.value = "";
      cargarHistorial();
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo procesar el archivo.");
    } finally {
      setSubiendo(false);
    }
  }

  return (
    <Layout
      titulo="Cargar bases"
      items={menuPorUsuario(user)}
    >
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <label className="block text-xs font-medium text-gray-500 mb-2">Tipo de archivo</label>
        <select
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="w-full sm:w-96 rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white mb-4"
        >
          {TIPOS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>


        {tipo === "REPORTE_KPI" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4 rounded-xl border border-gray-200 bg-gray-50 p-4">
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">Formato del KPI *</label>
              <select
                value={formatoKpi}
                onChange={(e) => setFormatoKpi(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
              >
                <option value="DETALLADO">Avance semanal Fijo Claro/VTR · formato detallado con NUM_PEDIDO</option>
                <option value="AVANCE_MOVIL">Avance semanal Móvil · formato agregado sin NUM_PEDIDO</option>
                <option value="CIERRE_FIJO">Cierre oficial Fijo · formato detallado con NUM_PEDIDO</option>
                <option value="CIERRE_MOVIL">Cierre oficial Móvil · formato agregado sin NUM_PEDIDO</option>
              </select>
              <p className="text-[11px] text-gray-400 mt-1">No edites el Excel para hacerlo coincidir con otro formato. El sistema usa el importador correcto según esta selección.</p>
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">Estado del reporte *</label>
              <select
                value={["DETALLADO", "AVANCE_MOVIL"].includes(formatoKpi) ? "AVANCE" : "CIERRE"}
                disabled
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-gray-100"
              >
                <option value="AVANCE">Avance semanal · puede seguir cambiando</option>
                <option value="CIERRE">Cierre oficial · queda congelado por canal</option>
              </select>
              <p className="text-[11px] text-gray-400 mt-1">
                {formatoKpi === "DETALLADO"
                  ? "Avance Fijo: actualiza solo la medición Fijo vigente y sus accionables."
                  : formatoKpi === "AVANCE_MOVIL"
                    ? "Avance Móvil: queda separado del Fijo y puede seguir cambiando con nuevos reportes."
                    : formatoKpi === "CIERRE_FIJO"
                      ? "Cierre Fijo: queda congelado con detalle por NUM_PEDIDO. No lo reemplaza un avance posterior."
                      : "Cierre Móvil: queda congelado por su canal y no alimenta accionables del KPI Fijo."}
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Fecha de corte Claro *</label>
              <input
                type="date"
                value={fechaCorte}
                onChange={(e) => setFechaCorte(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
              />
              <p className="text-[11px] text-gray-400 mt-1">Ej.: si el correo dice “pagos hasta el 31/07/2026”, usa 31/07/2026.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Día del reporte</label>
              <select
                value={diaReporte}
                onChange={(e) => setDiaReporte(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
              >
                <option value="LUNES">Lunes</option>
                <option value="MIERCOLES">Miércoles</option>
                <option value="OTRO">Otro</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <p className="text-xs font-medium text-gray-500 mb-2">{["DETALLADO", "AVANCE_MOVIL"].includes(formatoKpi) ? "Avance informado en el correo (opcional)" : "Cierre informado en el correo (opcional)"}</p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  ["1ª boleta", avanceB1, setAvanceB1],
                  ["2ª boleta", avanceB2, setAvanceB2],
                  ["3ª boleta", avanceB3, setAvanceB3],
                ].map(([label, value, setter]) => (
                  <div key={label}>
                    <label className="block text-[11px] text-gray-400 mb-1">{label} (%)</label>
                    <input
                      inputMode="decimal"
                      value={value}
                      onChange={(e) => setter(e.target.value)}
                      placeholder="Ej. 101,80"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
                    />
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-gray-400 mt-2">
                {formatoKpi === "AVANCE_MOVIL"
                  ? "Se guarda como referencia Claro del canal Móvil. El KPI Móvil se calcula con los RGU del reporte y su meta Móvil informada, sin reutilizar la meta Fijo."
                  : "Se guarda como referencia oficial de Claro. El KPI individual del Ejecutivo se calcula con sus RGU del snapshot y se compara contra la meta ESACOM de Fijo."}
              </p>
            </div>
            <div className="md:col-span-2 border-t border-gray-200 pt-3">
              <p className="text-xs font-medium text-gray-500 mb-2">Meta informada en el reporte (opcional)</p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  ["Meta 1ª", metaB1, setMetaB1],
                  ["Meta 2ª", metaB2, setMetaB2],
                  ["Meta 3ª", metaB3, setMetaB3],
                ].map(([label, value, setter]) => (
                  <div key={label}>
                    <label className="block text-[11px] text-gray-400 mb-1">{label} (%)</label>
                    <input inputMode="decimal" value={value} onChange={(e) => setter(e.target.value)} placeholder="Ej. 83,00" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white" />
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-gray-400 mt-2">
                {formatoKpi === "AVANCE_MOVIL" || formatoKpi === "CIERRE_MOVIL"
                  ? "Móvil usa la meta informada en su propio reporte (por ejemplo 87/84/78). No se aplican automáticamente las metas Fijo."
                  : "Fijo usa la meta ESACOM configurada por Soporte según la camada mensual, sin reescribir meses anteriores."}
              </p>
            </div>
          </div>
        )}

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center bg-gray-50"
        >
          <p className="text-sm text-gray-500 mb-2">
            {archivo ? (
              <span className="font-medium text-gray-900">{archivo.name}</span>
            ) : (
              "Arrastra el Excel aquí, o"
            )}
          </p>
          <button
            onClick={() => inputRef.current?.click()}
            className="text-xs font-medium text-esacom-red hover:underline"
          >
            elegir archivo
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(e) => setArchivo(e.target.files?.[0] || null)}
          />
        </div>

        <button
          onClick={handleSubir}
          disabled={!archivo || subiendo}
          className="mt-4 text-xs font-semibold bg-esacom-red text-white rounded-lg px-4 py-2
                     hover:bg-esacom-red-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {subiendo ? "Procesando... puede tardar hasta un minuto" : (tipo === "REPORTE_KPI" ? "Cargar reporte KPI" : "Cargar bases")}
        </button>

        {error && (
          <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3 mt-4">{error}</p>
        )}

        {resultado && (
          <div className="mt-4 bg-green-50 rounded-lg p-4">
            <p className="text-sm font-medium text-esacom-green mb-2">Importación completada</p>

            {resultado.formato === "CIERRE_FIJO" && (
              <div className="mb-3 rounded-lg bg-white px-3 py-2 text-sm text-gray-700">
                ✓ Cierre oficial Fijo importado con detalle NUM_PEDIDO. Queda separado del cierre Móvil y no desplaza el último AVANCE vigente.
              </div>
            )}

            {resultado.formato === "AVANCE_MOVIL" && (
              <div className="mb-3 space-y-3">
                <div className="rounded-lg bg-white px-3 py-2 text-sm text-gray-700">
                  ✓ Avance Claro Móvil importado sin exigir NUM_PEDIDO. Queda separado del AVANCE Fijo y no modifica sus accionables.
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  {["B1", "B2", "B3"].map((b) => {
                    const r = resultado.resumen_boletas?.[b] || resultado.avances?.[b];
                    if (!r) return null;
                    return (
                      <div key={b} className="rounded-lg bg-white p-3 text-xs">
                        <p className="font-bold text-gray-900">{b} · {r.camada}</p>
                        <p className="mt-1 text-gray-500">KPI pago <b className="text-gray-900">{Number(r.kpi_pago_pct || 0).toFixed(2)}%</b></p>
                        <p className="text-gray-500">Avance Claro <b className="text-gray-900">{r.cierre_claro_pct != null ? `${Number(r.cierre_claro_pct).toFixed(2)}%` : "—"}</b></p>
                        <p className="text-gray-500">Pago {r.pago} / {r.total_rgu} RGU</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {resultado.formato === "CIERRE_MOVIL" && (
              <div className="mb-3 space-y-3">
                <div className="rounded-lg bg-white px-3 py-2 text-sm text-gray-700">
                  ✓ Cierre Claro Móvil importado sin exigir NUM_PEDIDO. La ventana de AVANCE y los accionables vigentes no se modifican.
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  {["B1", "B2", "B3"].map((b) => {
                    const r = resultado.resumen_boletas?.[b] || resultado.cierres?.[b];
                    if (!r) return null;
                    return (
                      <div key={b} className="rounded-lg bg-white p-3 text-xs">
                        <p className="font-bold text-gray-900">{b} · {r.camada}</p>
                        <p className="mt-1 text-gray-500">KPI pago <b className="text-gray-900">{Number(r.kpi_pago_pct || 0).toFixed(2)}%</b></p>
                        <p className="text-gray-500">Cierre Claro <b className="text-gray-900">{r.cierre_claro_pct != null ? `${Number(r.cierre_claro_pct).toFixed(2)}%` : "—"}</b></p>
                        <p className="text-gray-500">Pago {r.pago} / {r.total_rgu} RGU</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {"coincidencias" in resultado && (
              <>
                <div
                  className={`rounded-lg px-3 py-2 mb-3 text-sm ${
                    resultado.coincidencias > 0 ? "bg-white text-gray-700" : "bg-orange-50 text-esacom-orange"
                  }`}
                >
                  {resultado.coincidencias > 0 ? (
                    <>
                      ✓ <strong>{resultado.coincidencias.toLocaleString("es-CL")}</strong> filas KPI se cruzaron
                      con ventas ESACOM usando <strong>NUM_PEDIDO + CAMADA + N_BOLETA</strong>.
                    </>
                  ) : (
                    <>
                      ⚠ Este reporte no cruzó con ninguna venta cargada (0 coincidencias de{" "}
                      {resultado.filas_leidas?.toLocaleString("es-CL")} filas leídas).
                    </>
                  )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3 text-xs">
                  <div className="bg-white rounded-lg p-3">
                    <p className="text-gray-400">Cortes nuevos</p>
                    <p className="text-lg font-semibold text-gray-900">{resultado.cortes_creados ?? 0}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3">
                    <p className="text-gray-400">Actualizados</p>
                    <p className="text-lg font-semibold text-gray-900">{resultado.cortes_actualizados ?? 0}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3">
                    <p className="text-gray-400">Sin venta ESACOM</p>
                    <p className="text-lg font-semibold text-esacom-orange">{resultado.sin_venta_propia ?? 0}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3">
                    <p className="text-gray-400">Filas con diferencias</p>
                    <p className="text-lg font-semibold text-esacom-red">
                      {resultado.filas_con_inconsistencia ??
                        ((resultado.diferencias_rut ?? 0) + (resultado.diferencias_rgu ?? 0) +
                          (resultado.diferencias_propietario ?? 0) + (resultado.diferencias_estado ?? 0))}
                    </p>
                  </div>
                </div>

                <div className="bg-white rounded-lg px-3 py-2 mb-3 text-xs text-gray-600">
                  <span className="font-medium">Validaciones:</span>{" "}
                  RUT {resultado.diferencias_rut ?? 0} · RGU {resultado.diferencias_rgu ?? 0} · Propietario/CE{" "}
                  {resultado.diferencias_propietario ?? 0} · Estado Claro/ESACOM {resultado.diferencias_estado ?? 0} ·
                  Fuera de medición {resultado.fuera_medicion ?? 0} · Ejecutivo KPI sin resolver{" "}
                  {resultado.ejecutivos_kpi_no_resueltos ?? 0}
                </div>
              </>
            )}

            {"coincidencias" in resultado && (
              <button
                onClick={() => navigate("/auditoria-kpi")}
                className="mb-3 text-xs font-semibold rounded-lg border border-green-700 text-green-800 px-3 py-2 hover:bg-white"
              >
                Revisar Auditoría KPI →
              </button>
            )}
            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer">Ver detalle técnico</summary>
              <pre className="mt-2 whitespace-pre-wrap font-mono">{JSON.stringify(resultado, null, 2)}</pre>
            </details>
          </div>
        )}
      </div>

      <h2 className="text-sm font-semibold text-gray-900 mb-3">Historial de cargas</h2>
      {historial === null && <div className="h-32 rounded-xl bg-gray-100 animate-pulse" />}
      {historial?.length === 0 && (
        <p className="text-sm text-gray-400">Todavía no hay cargas registradas.</p>
      )}
      {historial && historial.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs text-gray-500">
                <th className="text-left px-4 py-2 font-medium">Fecha</th>
                <th className="text-left px-4 py-2 font-medium">Estado KPI</th>
                <th className="text-left px-4 py-2 font-medium">Tipo</th>
                <th className="text-left px-4 py-2 font-medium">Origen</th>
                <th className="text-left px-4 py-2 font-medium">Archivo</th>
                <th className="text-right px-4 py-2 font-medium">Filas</th>
                <th className="text-right px-4 py-2 font-medium">Sin cruce</th>
                <th className="text-right px-4 py-2 font-medium">Alertas</th>
              </tr>
            </thead>
            <tbody>
              {historial.map((c) => (
                <tr key={c.id} className="border-b border-gray-100 last:border-0 text-xs">
                  <td className="px-4 py-2 text-gray-500">{new Date(c.creado_en).toLocaleString("es-CL")}</td>
                  <td className="px-4 py-2">{c.tipo_base === "REPORTE_KPI" ? <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${c.estado_reporte === "CIERRE" ? "bg-green-50 text-green-700" : "bg-blue-50 text-blue-700"}`}>{c.estado_reporte || "AVANCE"}</span> : <span className="text-gray-300">—</span>}</td>
                  <td className="px-4 py-2 text-gray-700">{c.tipo_base}</td>
                  <td className="px-4 py-2 text-gray-500">{c.origen}</td>
                  <td className="px-4 py-2 text-gray-700">
                    <div>{c.archivo_nombre}</div>
                    {c.fecha_corte && (
                      <>
                        <div className="text-[10px] text-gray-400">Corte: {c.fecha_corte} · {c.dia_reporte || "—"}</div>
                        <div className="text-[10px] text-gray-400">
                          Formato: {c.formato_kpi === "AVANCE_MOVIL"
                            ? "Avance Claro Móvil"
                            : c.formato_kpi === "CIERRE_MOVIL"
                              ? "Cierre Claro Móvil"
                              : c.formato_kpi === "CIERRE_FIJO"
                                ? "Cierre Claro Fijo"
                                : "Avance detallado Claro/VTR"}
                        </div>
                        <div className="text-[10px] text-gray-400">
                          {c.estado_reporte === "CIERRE" ? "Cierre" : "Avance"}: B1 {c.avance_b1 ?? "—"}% · B2 {c.avance_b2 ?? "—"}% · B3 {c.avance_b3 ?? "—"}%
                        </div>
                        <div className="text-[10px] text-gray-400">
                          Meta: B1 {c.meta_b1 ?? "—"}% · B2 {c.meta_b2 ?? "—"}% · B3 {c.meta_b3 ?? "—"}%
                        </div>
                      </>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-700">{c.filas_totales}</td>
                  <td className="px-4 py-2 text-right text-esacom-orange">{c.filas_sin_cruce}</td>
                  <td className="px-4 py-2 text-right text-esacom-red">{c.filas_con_error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
