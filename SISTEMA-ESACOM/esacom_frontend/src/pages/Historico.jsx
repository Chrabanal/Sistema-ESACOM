import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import Layout from "../components/Layout";
import { ADMIN_URL } from "../api/client";
import { fetchHistorico } from "../api/dashboard";
import { fetchHistorialCargas } from "../api/apelaciones";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

function nombreMes(camada) {
  const [anio, mes] = camada.split("-");
  const nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  return `${nombres[parseInt(mes, 10) - 1]} ${anio}`;
}

export default function Historico() {
  const { user } = useAuth();
  const [camadas, setCamadas] = useState(null);
  const [cargasKpi, setCargasKpi] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let activo = true;
    setError("");

    // El histórico por camadas respeta el alcance del usuario (equipo para
    // Supervisor, global para Gerencia). El historial administrativo de
    // archivos KPI sigue siendo exclusivo de Gerencia; no dejamos que un 403
    // de ese endpoint haga caer toda la pantalla del Supervisor.
    fetchHistorico()
      .then((datos) => { if (activo) setCamadas(datos); })
      .catch(() => { if (activo) setError("No se pudo cargar el histórico."); });

    if (user?.permisos?.historico) {
      fetchHistorialCargas({ tipo_base: "REPORTE_KPI", page_size: 100 })
        .then((cargas) => { if (activo) setCargasKpi(cargas); })
        .catch(() => { if (activo) setCargasKpi([]); });
    } else {
      setCargasKpi([]);
    }

    return () => { activo = false; };
  }, [user?.cargo]);

  const datosGrafico = (camadas || []).map((c) => ({
    mes: nombreMes(c.camada),
    Pagadas: c.pagadas,
    Pendientes: c.pendientes,
    "No Pago": c.no_pago,
    "Fuera Plazo": c.fuera_plazo,
  }));

  return (
    <Layout
      titulo="Histórico - comparativo mes a mes"
      items={menuPorUsuario(user)}
    >
      <p className="text-sm text-gray-500 mb-4">
        {user?.cargo === "SUPERVISOR"
          ? "Comparativo histórico de las ventas y estados de pago correspondientes exclusivamente a tu equipo ESACOM."
          : "Cada camada es el mes en que se vendió el cliente. Los reportes KPI quedan guardados como snapshots para consultar su evolución sin volver a abrir los Excel."}
      </p>

      {cargasKpi && cargasKpi.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto mb-6">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Histórico de reportes KPI Claro</h2>
            <p className="text-[11px] text-gray-400 mt-1">Snapshots recibidos por fecha de corte y día de envío.</p>
          </div>
          <table className="w-full text-xs">
            <thead><tr className="bg-gray-50 text-gray-500">
              <th className="text-left px-4 py-2">Corte</th><th className="text-left px-3 py-2">Día</th><th className="text-left px-3 py-2">Estado</th><th className="text-left px-3 py-2">Archivo</th>
              <th className="text-right px-3 py-2">Informado B1</th><th className="text-right px-3 py-2">Informado B2</th><th className="text-right px-3 py-2">Informado B3</th>
              <th className="text-right px-3 py-2">Meta B1</th><th className="text-right px-3 py-2">Meta B2</th><th className="text-right px-4 py-2">Meta B3</th>
            </tr></thead>
            <tbody>{cargasKpi.map((c) => (
              <tr key={c.id} className="border-t border-gray-100">
                <td className="px-4 py-2 font-medium">{c.fecha_corte || "—"}</td><td className="px-3 py-2">{c.dia_reporte || "—"}</td><td className="px-3 py-2 font-semibold">{c.estado_reporte || "AVANCE"}</td><td className="px-3 py-2 text-gray-500">{c.archivo_nombre}</td>
                {[c.avance_b1,c.avance_b2,c.avance_b3,c.meta_b1,c.meta_b2,c.meta_b3].map((v,i) => <td key={i} className="px-3 py-2 text-right">{v != null ? `${Number(v).toFixed(2)}%` : "—"}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {error && <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3">{error}</p>}

      {!error && camadas === null && <div className="h-96 rounded-xl bg-gray-100 animate-pulse" />}

      {!error && camadas?.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-400">
          Todavía no hay ventas cargadas para comparar.
        </div>
      )}

      {!error && camadas && camadas.length > 0 && (
        <>
          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6" style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={datosGrafico}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0F0F0" />
                <XAxis dataKey="mes" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Pagadas" stackId="a" fill="#1E8E3E" />
                <Bar dataKey="Pendientes" stackId="a" fill="#2563EB" />
                <Bar dataKey="No Pago" stackId="a" fill="#DA291C" />
                <Bar dataKey="Fuera Plazo" stackId="a" fill="#E8710A" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs text-gray-500 bg-gray-50">
                  <th className="text-left px-4 py-2 font-medium">Mes</th>
                  <th className="text-right px-4 py-2 font-medium">Ventas</th>
                  <th className="text-right px-4 py-2 font-medium">RGU</th>
                  <th className="text-right px-4 py-2 font-medium">Clientes</th>
                  <th className="text-right px-4 py-2 font-medium">RGU Pagados</th>
                  <th className="text-right px-4 py-2 font-medium">RGU Pendientes</th>
                  <th className="text-right px-4 py-2 font-medium">RGU No Pago</th>
                  <th className="text-right px-4 py-2 font-medium">Fuera medición</th>
                  <th className="text-right px-4 py-2 font-medium">% Cumplimiento</th>
                </tr>
              </thead>
              <tbody>
                {[...camadas].reverse().map((c, i, arr) => {
                  const anterior = arr[i + 1];
                  const delta = anterior ? c.ventas - anterior.ventas : null;
                  return (
                    <tr key={c.camada} className="border-b border-gray-100 last:border-0">
                      <td className="px-4 py-2 font-medium text-gray-900">{nombreMes(c.camada)}</td>
                      <td className="px-4 py-2 text-right text-gray-700">
                        {c.ventas}
                        {delta !== null && (
                          <span className={`ml-1 text-[11px] ${delta >= 0 ? "text-esacom-green" : "text-esacom-red"}`}>
                            ({delta >= 0 ? "+" : ""}{delta})
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-700">{c.rgu}</td>
                      <td className="px-4 py-2 text-right text-gray-700">{c.clientes}</td>
                      <td className="px-4 py-2 text-right text-esacom-green">{c.pagadas}</td>
                      <td className="px-4 py-2 text-right text-esacom-blue">{c.pendientes}</td>
                      <td className="px-4 py-2 text-right text-esacom-red">{c.no_pago}</td>
                      <td className="px-4 py-2 text-right text-gray-400">{c.fuera_medicion ?? 0}</td>
                      <td className="px-4 py-2 text-right font-medium text-gray-900">{c.pct_cumplimiento.toFixed(2)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Layout>
  );
}
