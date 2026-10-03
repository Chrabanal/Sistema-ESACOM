import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import client from "../api/client";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

function Estado({ ok, children }) {
  return <span className={`text-xs font-semibold ${ok ? "text-green-700" : "text-red-600"}`}>{ok ? "✓" : "✕"} {children}</span>;
}

export default function EstadoSistema() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function cargar() {
    setLoading(true); setError("");
    try { const r = await client.get("/estado-sistema/"); setData(r.data); }
    catch { setError("No se pudo consultar el estado del ambiente."); }
    finally { setLoading(false); }
  }
  useEffect(() => { cargar(); }, []);

  return <Layout titulo="Estado del sistema" items={menuPorUsuario(user)}>
    <div className="rounded-2xl border border-gray-200 bg-white p-5 mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <p className="font-semibold text-gray-900">Control previo a UAT general</p>
        <p className="text-sm text-gray-500 mt-1">No muestra secretos. Sirve para verificar datos, snapshot, integración y ambiente antes de probar todos los perfiles.</p>
      </div>
      <button onClick={cargar} className="rounded-xl bg-gray-900 text-white text-xs font-semibold px-4 py-2.5">↻ Actualizar</button>
    </div>
    {loading && <p className="text-sm text-gray-400">Consultando ambiente…</p>}
    {error && <p className="rounded-xl bg-red-50 text-red-700 p-3 text-sm">{error}</p>}
    {data && <>
      <div className={`rounded-2xl border p-5 mb-4 ${data.listo_uat ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}>
        <p className="text-lg font-bold text-gray-900">{data.listo_uat ? "Ambiente listo para UAT" : "Hay condiciones pendientes para UAT"}</p>
        <p className="text-sm text-gray-600 mt-1">Producción: {data.listo_produccion ? "preparada" : "aún no"}. Es correcto que durante UAT local siga pendiente PostgreSQL/HTTPS.</p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
        {Object.entries(data.checks || {}).map(([k,v]) => <div key={k} className="rounded-2xl bg-white border border-gray-200 p-4"><Estado ok={v}>{k.replaceAll("_"," ")}</Estado></div>)}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <section className="rounded-2xl bg-white border border-gray-200 p-5">
          <h2 className="font-bold text-gray-900">Ambiente</h2>
          <div className="text-sm text-gray-600 mt-3 space-y-2">
            <p>Base de datos: <b>{data.ambiente?.base_datos}</b></p>
            <p>DEBUG: <b>{String(data.ambiente?.debug)}</b></p>
            <p>Celery eager: <b>{String(data.ambiente?.celery_eager)}</b></p>
            <p>HTTPS forzado: <b>{String(data.ambiente?.https_forzado)}</b></p>
          </div>
        </section>
        <section className="rounded-2xl bg-white border border-gray-200 p-5">
          <h2 className="font-bold text-gray-900">Snapshot KPI activo</h2>
          <div className="text-sm text-gray-600 mt-3 space-y-2">
            <p>Archivo: <b>{data.snapshot?.archivo || "Sin snapshot"}</b></p>
            <p>Corte: <b>{data.snapshot?.fecha_corte || "—"}</b> · {data.snapshot?.dia || "—"}</p>
            <p>Focos: B1 <b>{data.snapshot?.focos?.B1 || "—"}</b> · B2 <b>{data.snapshot?.focos?.B2 || "—"}</b> · B3 <b>{data.snapshot?.focos?.B3 || "—"}</b></p>
          </div>
        </section>
        <section className="rounded-2xl bg-white border border-gray-200 p-5">
          <h2 className="font-bold text-gray-900">Integración Google</h2>
          <div className="mt-3 space-y-2">
            <Estado ok={data.integraciones?.google_sheets_id_configurado}>Spreadsheet ID configurado</Estado><br/>
            <Estado ok={data.integraciones?.credencial_google_configurada}>Credencial configurada</Estado><br/>
            <Estado ok={data.integraciones?.credencial_google_existe}>Archivo de credencial disponible</Estado>
          </div>
        </section>
        <section className="rounded-2xl bg-white border border-gray-200 p-5">
          <h2 className="font-bold text-gray-900">Usuarios por rol</h2>
          <div className="grid grid-cols-2 gap-2 mt-3 text-sm">
            {Object.entries(data.datos?.roles || {}).map(([k,v]) => <div key={k} className="rounded-xl bg-gray-50 p-3"><p className="font-semibold text-gray-800">{k}</p><p className="text-gray-500">{v.activos} activos · {v.total} total</p></div>)}
          </div>
        </section>
      </div>
    </>}
  </Layout>;
}
