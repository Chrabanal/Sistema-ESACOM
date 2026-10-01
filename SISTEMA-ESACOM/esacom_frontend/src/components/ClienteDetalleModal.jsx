import { useEffect, useState } from "react";
import { fetchVentaDetalle, registrarGestion } from "../api/apelaciones";

const ESTADO_PAGO = {
  PAGADO: "bg-green-50 text-green-700",
  PENDIENTE: "bg-blue-50 text-blue-700",
  NO_PAGO: "bg-red-50 text-red-700",
  FUERA_PLAZO: "bg-orange-50 text-orange-700",
  SIN_BOLETA: "bg-gray-100 text-gray-600",
};

export default function ClienteDetalleModal({ ventaId, onClose, permitirGestion = false }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ tipo: "LLAMADA", resultado: "CONTACTADO", nota: "", proximo_contacto: "" });
  const [guardando, setGuardando] = useState(false);

  const cargar = () => {
    setError("");
    fetchVentaDetalle(ventaId).then(setData).catch(() => setError("No se pudo cargar el detalle del cliente."));
  };

  useEffect(() => { if (ventaId) cargar(); }, [ventaId]);
  if (!ventaId) return null;

  async function guardarGestion(e) {
    e.preventDefault();
    setGuardando(true);
    try {
      await registrarGestion(ventaId, form.tipo, {
        resultado: form.resultado,
        nota: form.nota,
        proximo_contacto: form.proximo_contacto || null,
      });
      setForm({ tipo: "LLAMADA", resultado: "CONTACTADO", nota: "", proximo_contacto: "" });
      cargar();
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo registrar la gestión.");
    } finally {
      setGuardando(false);
    }
  }

  const v = data?.venta;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4" onMouseDown={onClose}>
      <div className="bg-white w-full sm:max-w-4xl max-h-[94dvh] sm:max-h-[92vh] overflow-y-auto rounded-t-3xl sm:rounded-2xl shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-white/95 backdrop-blur border-b border-gray-200 px-4 sm:px-5 py-4 flex items-center justify-between z-10">
          <div>
            <p className="text-xs text-gray-400">Detalle de cliente</p>
            <h2 className="font-semibold text-gray-900">{v?.nombre_cliente || v?.rut_cliente || "Cargando..."}</h2>
          </div>
          <button onClick={onClose} className="w-10 h-10 rounded-full bg-gray-100 text-gray-500 hover:text-gray-800 text-xl flex items-center justify-center">×</button>
        </div>

        <div className="p-4 sm:p-5 space-y-5 pb-[max(1rem,env(safe-area-inset-bottom))]">
          {error && <div className="bg-red-50 text-red-700 text-sm rounded-lg px-3 py-2">{error}</div>}
          {!data && !error && <div className="h-48 bg-gray-100 rounded-xl animate-pulse" />}
          {data && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3 text-xs">
                {[
                  ["RUT", v.rut_cliente], ["Pedido", v.n_pedido], ["Teléfono", v.telefono_cliente || "—"],
                  ["Camada", v.camada], ["Producto", v.promocion?.nombre || "—"], ["RGU base", v.rgu_base ?? "—"],
                  ["Fecha venta", v.fecha_venta], ["Fecha cierre", v.fecha_cierre || "—"],
                ].map(([label, value]) => <div key={label} className="bg-gray-50 rounded-lg p-3"><p className="text-gray-400">{label}</p><p className="font-medium text-gray-800 mt-1">{value}</p></div>)}
              </div>

              <section>
                <div className="flex items-center justify-between mb-2"><h3 className="text-sm font-semibold text-gray-900">Boletas / KPI</h3><span className="text-xs text-gray-400">{data.cortes.length} corte(s)</span></div>
                <div className="sm:hidden space-y-2">
                  {data.cortes.map((c) => (
                    <div key={`m-${c.id}`} className="rounded-2xl border border-gray-200 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div><p className="text-xs font-semibold text-gray-900">{c.mes_ano} · {c.boleta}</p><p className="text-[11px] text-gray-400 mt-0.5">Vence {c.fecha_vencimiento || "—"}</p></div>
                        <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full ${ESTADO_PAGO[c.estado_pago] || "bg-gray-100"}`}>{c.estado_pago}</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                        <div className="rounded-xl bg-gray-50 p-2"><p className="text-[9px] uppercase text-gray-400">Pago</p><p className="text-xs font-semibold">{c.fecha_pago || "—"}</p></div>
                        <div className="rounded-xl bg-gray-50 p-2"><p className="text-[9px] uppercase text-gray-400">RGU</p><p className="text-xs font-semibold">{c.rgu_kpi ?? v.rgu_base ?? "—"}</p></div>
                        <div className="rounded-xl bg-gray-50 p-2"><p className="text-[9px] uppercase text-gray-400">Claro</p><p className={`text-[10px] font-semibold ${c.estado_claro && c.estado_claro !== c.estado_pago ? "text-red-600" : "text-gray-700"}`}>{c.estado_claro || "—"}</p></div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="hidden sm:block overflow-x-auto border border-gray-200 rounded-xl">
                  <table className="w-full text-xs min-w-[720px]">
                    <thead className="bg-gray-50 text-gray-500"><tr><th className="text-left px-3 py-2">Corte</th><th className="text-left px-3 py-2">Estado</th><th className="text-left px-3 py-2">Vencimiento</th><th className="text-left px-3 py-2">Pago</th><th className="text-right px-3 py-2">RGU</th><th className="text-left px-3 py-2">Claro / ESACOM</th></tr></thead>
                    <tbody>{data.cortes.map((c) => <tr key={c.id} className="border-t border-gray-100"><td className="px-3 py-2">{c.mes_ano} · {c.boleta}</td><td className="px-3 py-2"><span className={`px-2 py-1 rounded-full ${ESTADO_PAGO[c.estado_pago] || "bg-gray-100"}`}>{c.estado_pago}</span></td><td className="px-3 py-2">{c.fecha_vencimiento || "—"}</td><td className="px-3 py-2">{c.fecha_pago || "—"}</td><td className="px-3 py-2 text-right">{c.rgu_kpi ?? v.rgu_base ?? "—"}</td><td className="px-3 py-2"><span className={c.estado_claro && c.estado_claro !== c.estado_pago ? "text-red-600 font-medium" : "text-gray-600"}>{c.estado_claro || "—"} / {c.estado_pago}</span></td></tr>)}</tbody>
                  </table>
                </div>
              </section>

              <section>
                <div className="flex items-center justify-between mb-2"><h3 className="text-sm font-semibold text-gray-900">Historial de gestión</h3><span className="text-xs text-gray-400">{data.gestiones.length} registro(s)</span></div>
                <div className="space-y-2 max-h-52 overflow-y-auto">
                  {data.gestiones.length === 0 && <p className="text-xs text-gray-400 border border-dashed border-gray-200 rounded-lg p-4">Todavía no hay gestiones registradas.</p>}
                  {data.gestiones.map((g) => <div key={g.id} className="border border-gray-200 rounded-lg p-3 text-xs"><div className="flex justify-between gap-4"><p className="font-medium text-gray-800">{g.tipo} · {g.resultado || "Sin resultado"}</p><p className="text-gray-400 whitespace-nowrap">{new Date(g.creado_en).toLocaleString("es-CL")}</p></div><p className="text-gray-600 mt-1">{g.nota || "Sin observación"}</p>{g.proximo_contacto && <p className="text-blue-600 mt-1">Próximo contacto: {new Date(g.proximo_contacto).toLocaleString("es-CL")}</p>}</div>)}
                </div>
              </section>

              {permitirGestion && (
                <form onSubmit={guardarGestion} className="border border-gray-200 rounded-2xl p-4 bg-gray-50">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Registrar gestión</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })} className="min-h-11 border border-gray-300 bg-white rounded-xl px-3 py-2 text-sm"><option value="LLAMADA">Llamada</option><option value="WHATSAPP">WhatsApp</option><option value="OTRO">Otro</option></select>
                    <select value={form.resultado} onChange={(e) => setForm({ ...form, resultado: e.target.value })} className="min-h-11 border border-gray-300 bg-white rounded-xl px-3 py-2 text-sm"><option value="CONTACTADO">Contactado</option><option value="NO_CONTESTA">No contesta</option><option value="COMPROMISO_PAGO">Compromiso de pago</option><option value="NUMERO_INVALIDO">Número inválido</option><option value="REAGENDAR">Reagendar</option><option value="OTRO">Otro</option></select>
                    <input type="datetime-local" value={form.proximo_contacto} onChange={(e) => setForm({ ...form, proximo_contacto: e.target.value })} className="min-h-11 border border-gray-300 bg-white rounded-xl px-3 py-2 text-sm" />
                    <input value={form.nota} onChange={(e) => setForm({ ...form, nota: e.target.value })} placeholder="Observación de la gestión" className="min-h-11 border border-gray-300 bg-white rounded-xl px-3 py-2 text-sm" />
                  </div>
                  <div className="mt-3 flex justify-end"><button disabled={guardando} className="w-full sm:w-auto min-h-11 bg-esacom-red text-white text-xs font-semibold px-5 py-2.5 rounded-xl disabled:opacity-50">{guardando ? "Guardando..." : "Guardar gestión"}</button></div>
                </form>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
