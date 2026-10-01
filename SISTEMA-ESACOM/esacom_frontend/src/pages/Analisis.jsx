import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
import { ADMIN_URL } from "../api/client";
import { fetchDashboardKpi, fetchHistorico, fetchKpiPorEjecutivo } from "../api/dashboard";
import { fetchHistorialCargas, fetchResumenAuditoriaKPI } from "../api/apelaciones";

function pct(v) {
  return `${Number(v || 0).toFixed(1)}%`;
}

function tendencia(camadas) {
  if (!camadas || camadas.length < 2) return null;
  const actual = camadas[camadas.length - 1];
  const anterior = camadas[camadas.length - 2];
  const kpi = (c) => {
    const den = (c.pagadas || 0) + (c.pendientes || 0) + (c.no_pago || 0) + (c.fuera_plazo || 0);
    return den ? ((c.pagadas || 0) / den) * 100 : 0;
  };
  return { actual, anterior, delta: kpi(actual) - kpi(anterior), kpiActual: kpi(actual), kpiAnterior: kpi(anterior) };
}

export default function Analisis() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetchDashboardKpi(),
      fetchHistorico(),
      fetchKpiPorEjecutivo(),
      fetchHistorialCargas({ tipo_base: "REPORTE_KPI", page_size: 1 }),
    ])
      .then(async ([cortes, historico, ejecutivos, cargas]) => {
        const ultima = cargas?.[0] || null;
        const auditoria = ultima ? await fetchResumenAuditoriaKPI({ carga: ultima.id }) : null;
        setData({ cortes, historico, ejecutivos, ultima, auditoria });
      })
      .catch(() => setError("No se pudo cargar el análisis gerencial."));
  }, []);

  const insights = useMemo(() => {
    if (!data) return null;
    const cortes = data.cortes || [];
    const peorCorte = [...cortes].sort((a, b) => (a.pct_cumplimiento || 0) - (b.pct_cumplimiento || 0))[0];
    const riesgos = (data.ejecutivos || [])
      .map((e) => {
        const cortesE = e.cortes || [];
        const medibles = cortesE.filter((c) => (c.total || 0) > 0);
        const promedio = medibles.length
          ? medibles.reduce((s, c) => s + (c.pct_cumplimiento || 0), 0) / medibles.length
          : 100;
        return { ...e, promedio };
      })
      .sort((a, b) => a.promedio - b.promedio)
      .slice(0, 5);
    return { peorCorte, riesgos, tendencia: tendencia(data.historico) };
  }, [data]);

  return (
    <Layout
      titulo="Análisis Gerencial"
      items={menuPorUsuario(user)}
    >
      {error && <div className="rounded-xl bg-red-50 text-red-700 p-4 text-sm">{error}</div>}
      {!error && !data && <div className="h-56 rounded-xl bg-gray-100 animate-pulse" />}
      {data && (
        <div className="space-y-5">
          <p className="text-sm text-gray-500">
            Lectura ejecutiva construida desde los KPI vigentes, histórico, desempeño por ejecutivo y la última auditoría cargada.
          </p>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-400">Último corte Claro</p>
              <p className="font-semibold mt-1">{data.ultima?.fecha_corte || "Sin carga"}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-400">Cruces KPI</p>
              <p className="text-2xl font-semibold text-green-700">{data.auditoria?.cruzados?.toLocaleString("es-CL") ?? "—"}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-400">Sin venta ESACOM</p>
              <p className="text-2xl font-semibold text-orange-600">{data.auditoria?.sin_cruce?.toLocaleString("es-CL") ?? "—"}</p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-xs text-gray-400">Inconsistencias a revisar</p>
              <p className="text-2xl font-semibold text-red-700">{data.auditoria?.filas_con_inconsistencia?.toLocaleString("es-CL") ?? "—"}</p>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <section className="bg-white border rounded-xl p-5">
              <h2 className="font-semibold text-gray-900">Lectura del KPI</h2>
              {insights?.peorCorte ? (
                <div className="mt-4 space-y-3 text-sm">
                  <div className="rounded-lg bg-red-50 p-3">
                    <p className="text-xs text-red-500">Foco con menor cumplimiento</p>
                    <p className="font-semibold text-red-800 mt-1">
                      {insights.peorCorte.boleta} · {insights.peorCorte.mes_ano}: {pct(insights.peorCorte.pct_cumplimiento)}
                    </p>
                  </div>
                  {insights.tendencia && (
                    <div className="rounded-lg bg-gray-50 p-3">
                      <p className="text-xs text-gray-400">Tendencia mensual estimada por RGU medible</p>
                      <p className="font-semibold mt-1">
                        {insights.tendencia.anterior.camada}: {pct(insights.tendencia.kpiAnterior)} → {insights.tendencia.actual.camada}: {pct(insights.tendencia.kpiActual)}
                      </p>
                      <p className={`text-xs mt-1 ${insights.tendencia.delta >= 0 ? "text-green-700" : "text-red-700"}`}>
                        {insights.tendencia.delta >= 0 ? "+" : ""}{insights.tendencia.delta.toFixed(1)} puntos porcentuales
                      </p>
                    </div>
                  )}
                </div>
              ) : <p className="text-sm text-gray-400 mt-3">Sin datos KPI medibles todavía.</p>}
            </section>

            <section className="bg-white border rounded-xl p-5">
              <h2 className="font-semibold text-gray-900">Auditoría última carga</h2>
              <div className="grid grid-cols-2 gap-2 mt-4 text-sm">
                {[
                  ["RUT", data.auditoria?.diferencia_rut],
                  ["RGU", data.auditoria?.diferencia_rgu],
                  ["Propietario / CE", data.auditoria?.diferencia_propietario],
                  ["Estado Claro / ESACOM", data.auditoria?.diferencia_estado],
                  ["Fuera de medición", data.auditoria?.fuera_medicion],
                  ["Ejecutivo sin resolver", data.auditoria?.ejecutivo_no_resuelto],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-gray-50 p-3 flex justify-between gap-2">
                    <span className="text-gray-500">{label}</span><strong>{value ?? "—"}</strong>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <section className="bg-white border rounded-xl overflow-hidden">
            <div className="p-5 border-b"><h2 className="font-semibold">Ejecutivos con mayor riesgo KPI</h2></div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-500"><tr>
                  <th className="text-left px-4 py-3">Ejecutivo</th>
                  <th className="text-left px-4 py-3">Equipo</th>
                  <th className="text-right px-4 py-3">Promedio focos</th>
                </tr></thead>
                <tbody className="divide-y">
                  {insights?.riesgos?.map((e) => (
                    <tr key={e.ejecutivo?.id || e.ejecutivo?.rut || e.ejecutivo?.nombre}>
                      <td className="px-4 py-3 font-medium">{e.ejecutivo?.nombre || "Sin nombre"}</td>
                      <td className="px-4 py-3 text-gray-500">{e.ejecutivo?.equipo || "—"}</td>
                      <td className="px-4 py-3 text-right font-semibold">{pct(e.promedio)}</td>
                    </tr>
                  ))}
                  {!insights?.riesgos?.length && <tr><td colSpan="3" className="p-6 text-center text-gray-400">Sin datos de ejecutivos.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </Layout>
  );
}
