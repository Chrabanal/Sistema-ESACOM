import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
import { fetchKpiPorEjecutivo } from "../api/dashboard";

const NOMBRE_BOLETA = { B1: "1\u00AA Boleta", B2: "2\u00AA Boleta", B3: "3\u00AA Boleta" };

const COLOR_CELDA = {
  verde: "bg-green-50 text-esacom-green",
  amarillo: "bg-orange-50 text-esacom-orange",
  rojo: "bg-esacom-red-light text-esacom-red",
  sin_datos: "bg-gray-50 text-gray-400",
};

function nombreCorte(mesAno, boleta) {
  const [anio, mes] = mesAno.split("-");
  const nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  return `${nombres[parseInt(mes, 10) - 1]} ${anio} \u00B7 ${NOMBRE_BOLETA[boleta] || boleta}`;
}

export default function SeguimientoEjecutivos() {
  const { user } = useAuth();
  const [ejecutivos, setEjecutivos] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [soloRiesgo, setSoloRiesgo] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchKpiPorEjecutivo()
      .then(setEjecutivos)
      .catch(() => setError("No se pudo cargar el seguimiento de ejecutivos."));
  }, []);

  const columnas = useMemo(() => {
    if (!ejecutivos) return [];
    const set = new Map();
    ejecutivos.forEach((e) =>
      e.cortes.forEach((c) => set.set(`${c.mes_ano}|${c.boleta}`, { mes_ano: c.mes_ano, boleta: c.boleta }))
    );
    return [...set.values()].sort((a, b) => (a.mes_ano + a.boleta < b.mes_ano + b.boleta ? 1 : -1));
  }, [ejecutivos]);

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return (ejecutivos || []).filter((e) => {
      const coincide = !q || e.ejecutivo.nombre.toLowerCase().includes(q) ||
        (e.ejecutivo.equipo || "").toLowerCase().includes(q) ||
        (e.ejecutivo.rut || "").toLowerCase().includes(q);
      const riesgo = !soloRiesgo || e.cortes.some((c) => c.semaforo === "rojo" || c.semaforo === "amarillo");
      return coincide && riesgo;
    });
  }, [ejecutivos, busqueda, soloRiesgo]);

  const riesgo = (ejecutivos || []).filter((e) => e.cortes.some((c) => c.semaforo === "rojo" || c.semaforo === "amarillo")).length;

  return (
    <Layout
      titulo="Seguimiento a ejecutivos"
      items={menuPorUsuario(user)}
    >
      {error && <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3">{error}</p>}

      {!error && ejecutivos === null && <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />}

      {!error && ejecutivos?.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-400">
          No hay ejecutivos con cortes registrados todav\u00EDa.
        </div>
      )}

      {!error && ejecutivos && ejecutivos.length > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-400">Ejecutivos medidos</p>
              <p className="text-2xl font-semibold text-gray-900">{ejecutivos.length}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-400">Con foco de riesgo</p>
              <p className="text-2xl font-semibold text-esacom-red">{riesgo}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4 col-span-2 md:col-span-1">
              <p className="text-xs text-gray-400">Cortes visibles</p>
              <p className="text-2xl font-semibold text-gray-900">{columnas.length}</p>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4 flex flex-col sm:flex-row gap-3 sm:items-center">
            <input
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar ejecutivo, RUT o equipo..."
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <label className="flex items-center gap-2 text-xs text-gray-600 whitespace-nowrap">
              <input type="checkbox" checked={soloRiesgo} onChange={(e) => setSoloRiesgo(e.target.checked)} />
              Solo con riesgo
            </label>
            <span className="text-xs text-gray-400">{filtrados.length} resultado(s)</span>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left font-medium text-gray-500 text-xs px-4 py-3 sticky left-0 bg-white z-10">
                    Ejecutivo
                  </th>
                  {columnas.map((col) => (
                    <th key={`${col.mes_ano}-${col.boleta}`} className="text-center font-medium text-gray-500 text-xs px-4 py-3 whitespace-nowrap">
                      {nombreCorte(col.mes_ano, col.boleta)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtrados.map((e) => (
                  <tr key={e.ejecutivo.id} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-3 sticky left-0 bg-white z-10">
                      <p className="font-medium text-gray-900">{e.ejecutivo.nombre}</p>
                      <p className="text-xs text-gray-400">{e.ejecutivo.equipo || "Sin equipo"} \u00B7 {e.ejecutivo.rut}</p>
                    </td>
                    {columnas.map((col) => {
                      const corte = e.cortes.find((c) => c.mes_ano === col.mes_ano && c.boleta === col.boleta);
                      if (!corte) return <td key={`${col.mes_ano}-${col.boleta}`} className="px-4 py-3 text-center text-gray-300">{"\u2014"}</td>;
                      return (
                        <td key={`${col.mes_ano}-${col.boleta}`} className="px-2 py-2">
                          <div className={`rounded-lg px-3 py-1.5 text-center ${COLOR_CELDA[corte.semaforo]}`}>
                            <p className="font-semibold">{corte.pct_cumplimiento.toFixed(2)}%</p>
                            <p className="text-[10px] opacity-75">RGU {corte.pagadas}/{corte.total}</p>
                            {(corte.fuera_medicion || 0) > 0 && <p className="text-[9px] opacity-60">{corte.fuera_medicion} fuera medici\u00F3n</p>}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {filtrados.length === 0 && (
                  <tr><td colSpan={columnas.length + 1} className="px-4 py-8 text-center text-gray-400">No hay ejecutivos para este filtro.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Layout>
  );
}

