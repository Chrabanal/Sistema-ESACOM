import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import ClienteDetalleModal from "../components/ClienteDetalleModal";
import { fetchCortes, verificarCorte } from "../api/apelaciones";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

const ESTADOS = [
  ["PENDIENTE", "Pendientes"], ["NO_PAGO", "No pago"], ["FUERA_PLAZO", "Fuera de plazo"], ["PAGADO", "Pagados"],
];

function rguEsacom(c) {
  return c.venta?.rgu_base ?? c.rgu_kpi ?? "—";
}

export default function Cobranza() {
  const { user } = useAuth();
  const [estado, setEstado] = useState("PENDIENTE");
  const [cortes, setCortes] = useState(null);
  const [q, setQ] = useState("");
  const [ejecutivoFiltro, setEjecutivoFiltro] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [procesando, setProcesando] = useState(null);
  const [error, setError] = useState("");

  const cargar = () => {
    setCortes(null); setError("");
    fetchCortes({ estado_pago: estado, page_size: 1000 }).then(setCortes).catch(() => setError("No se pudo cargar la cartera de cobranza."));
  };
  useEffect(cargar, [estado]);

  const ejecutivos = useMemo(() => {
    const mapa = new Map();
    (cortes || []).forEach((c) => {
      const e = c.venta?.ejecutivo;
      if (e?.id) mapa.set(String(e.id), e.nombre);
    });
    return [...mapa.entries()].sort((a,b) => a[1].localeCompare(b[1], "es"));
  }, [cortes]);

  const filtrados = useMemo(() => (cortes || []).filter((c) => {
    const e = c.venta?.ejecutivo;
    if (ejecutivoFiltro && String(e?.id || "") !== String(ejecutivoFiltro)) return false;
    const txt = `${c.venta?.rut_cliente || ""} ${c.venta?.nombre_cliente || ""} ${c.venta?.n_pedido || ""} ${e?.nombre || ""} ${c.propietario_final || ""}`.toLowerCase();
    return !q.trim() || txt.includes(q.trim().toLowerCase());
  }), [cortes, q, ejecutivoFiltro]);

  async function marcar(c, nuevo) {
    const etiqueta = nuevo === "PAGADO" ? "verificar como PAGADO" : "marcar como NO PAGO";
    if (!window.confirm(`¿Confirmas ${etiqueta} el pedido ${c.venta?.n_pedido || ""}?\nEsta acción quedará registrada con tu usuario.`)) return;
    setProcesando(c.id);
    try { await verificarCorte(c.id, nuevo); cargar(); }
    catch (e) { setError(e.response?.data?.detail || "No se pudo verificar el estado."); }
    finally { setProcesando(null); }
  }

  function exportar() {
    const filas = [["Pedido","RUT Cliente","Cliente","Camada","Boleta","Estado","Vencimiento","Pago","RGU ESACOM","Ejecutivo ESACOM","Propietario Claro"]];
    filtrados.forEach((c) => filas.push([
      c.venta?.n_pedido, c.venta?.rut_cliente, c.venta?.nombre_cliente, c.mes_ano, c.boleta, c.estado_pago,
      c.fecha_vencimiento||"", c.fecha_pago||"", rguEsacom(c), c.venta?.ejecutivo?.nombre||"", c.propietario_final||"",
    ]));
    const csv = filas.map((r) => r.map((x) => `"${String(x ?? "").replaceAll('"','""')}"`).join(";")).join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `COBRANZA_${estado}.csv`; a.click(); URL.revokeObjectURL(url);
  }

  return <Layout titulo="Gestión de Cobranza" items={menuPorUsuario(user)}> 
    <div className="mb-4 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
      <div><p className="text-sm text-gray-500">Cobranza operacional ESACOM. Puede incluir ventas posteriores al foco KPI oficial de Claro. El responsable mostrado siempre corresponde al dueño por RUT EVT de ESACOM.</p></div>
      <button onClick={exportar} disabled={!filtrados.length} className="min-h-11 text-xs font-semibold px-4 py-2 rounded-xl border border-gray-300 bg-white disabled:opacity-40">Exportar cartera</button>
    </div>

    <div className="flex gap-2 overflow-x-auto mb-4 pb-1">{ESTADOS.map(([v,l]) => <button key={v} onClick={() => setEstado(v)} className={`min-h-10 text-xs px-3 py-2 rounded-xl whitespace-nowrap ${estado===v?"bg-esacom-red text-white":"bg-white border border-gray-200 text-gray-600"}`}>{l}</button>)}</div>

    <div className="grid grid-cols-1 md:grid-cols-[1fr_320px] gap-3 mb-4">
      <input value={q} onChange={(e)=>setQ(e.target.value)} placeholder="Buscar cliente, pedido, RUT o ejecutivo..." className="min-h-11 w-full border border-gray-300 rounded-xl px-3 py-2 text-sm" />
      {(["GERENCIA","OPERACIONES","CONTABILIDAD"].includes(user?.cargo)) && <select value={ejecutivoFiltro} onChange={(e)=>setEjecutivoFiltro(e.target.value)} className="min-h-11 border border-gray-300 rounded-xl bg-white px-3 py-2 text-sm"><option value="">Todo el equipo</option>{ejecutivos.map(([id,nombre])=><option key={id} value={id}>{nombre}</option>)}</select>}
    </div>

    {error && <p className="mb-4 bg-red-50 text-red-700 rounded-xl px-3 py-2 text-sm">{error}</p>}
    {cortes===null ? <div className="h-64 rounded-xl bg-gray-100 animate-pulse"/> : <>
      <div className="md:hidden space-y-3">
        {filtrados.map((c) => <div key={`m-${c.id}`} className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm">
          <div className="flex items-start justify-between gap-3"><div><button onClick={()=>setDetalle(c.venta?.id)} className="font-semibold text-left text-sm text-gray-900">{c.venta?.nombre_cliente || c.venta?.rut_cliente}</button><p className="text-xs text-gray-400 mt-0.5">{c.venta?.rut_cliente} · {c.venta?.n_pedido}</p></div><span className="rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-semibold">{rguEsacom(c)} RGU</span></div>
          <div className="grid grid-cols-2 gap-2 mt-3 text-xs"><div className="bg-gray-50 rounded-xl p-2.5"><p className="text-[10px] uppercase text-gray-400">Corte</p><p className="font-medium">{c.mes_ano} · {c.boleta}</p></div><div className="bg-gray-50 rounded-xl p-2.5"><p className="text-[10px] uppercase text-gray-400">Vencimiento</p><p className="font-medium">{c.fecha_vencimiento||"—"}</p></div></div>
          <div className="mt-3 rounded-xl bg-blue-50 p-2.5"><p className="text-[10px] uppercase text-blue-400">Ejecutivo ESACOM</p><p className="text-xs font-semibold text-blue-800">{c.venta?.ejecutivo?.nombre||"—"}</p></div>
          {c.propietario_final && c.propietario_final !== c.venta?.ejecutivo?.nombre && <p className="mt-2 text-[10px] text-gray-400">Claro propietario: {c.propietario_final}</p>}
          <p className={`mt-2 text-xs ${c.estado_claro && c.estado_claro!==c.estado_pago?"text-red-600 font-semibold":"text-gray-600"}`}>Claro {c.estado_claro||"—"} · ESACOM {c.estado_pago}</p>
          <div className="grid grid-cols-2 gap-2 mt-3"><button disabled={procesando===c.id} onClick={()=>marcar(c,"PAGADO")} className="min-h-11 rounded-xl bg-green-50 text-green-700 text-xs font-semibold disabled:opacity-40">Verificar pago</button><button disabled={procesando===c.id} onClick={()=>marcar(c,"NO_PAGO")} className="min-h-11 rounded-xl bg-red-50 text-red-600 text-xs font-semibold disabled:opacity-40">No pago</button></div>
        </div>)}
        {!filtrados.length && <div className="p-8 text-center text-sm text-gray-400 bg-white border border-gray-200 rounded-2xl">Sin casos para este filtro.</div>}
      </div>

      <div className="hidden md:block bg-white border border-gray-200 rounded-xl overflow-x-auto"><table className="w-full min-w-[1050px] text-xs"><thead className="bg-gray-50 text-gray-500"><tr><th className="text-left px-3 py-2">Cliente</th><th className="text-left px-3 py-2">Pedido</th><th className="text-left px-3 py-2">Corte</th><th className="text-left px-3 py-2">Vencimiento</th><th className="text-right px-3 py-2">RGU</th><th className="text-left px-3 py-2">Ejecutivo ESACOM</th><th className="text-left px-3 py-2">Claro / ESACOM</th><th className="text-right px-3 py-2">Acción</th></tr></thead><tbody>{filtrados.map((c)=><tr key={c.id} className="border-t border-gray-100"><td className="px-3 py-2"><button onClick={()=>setDetalle(c.venta?.id)} className="font-medium text-left text-gray-800 hover:text-esacom-red">{c.venta?.nombre_cliente || c.venta?.rut_cliente}</button><p className="text-[10px] text-gray-400">{c.venta?.rut_cliente}</p></td><td className="px-3 py-2">{c.venta?.n_pedido}</td><td className="px-3 py-2">{c.mes_ano} · {c.boleta}</td><td className="px-3 py-2">{c.fecha_vencimiento||"—"}</td><td className="px-3 py-2 text-right">{rguEsacom(c)}</td><td className="px-3 py-2"><p className="font-medium">{c.venta?.ejecutivo?.nombre||"—"}</p>{c.propietario_final&&<p className="text-[10px] text-gray-400">Claro: {c.propietario_final}</p>}</td><td className="px-3 py-2"><span className={c.estado_claro && c.estado_claro!==c.estado_pago?"text-red-600 font-semibold":"text-gray-600"}>{c.estado_claro||"—"} / {c.estado_pago}</span></td><td className="px-3 py-2 text-right"><button disabled={procesando===c.id} onClick={()=>marcar(c,"PAGADO")} className="text-green-700 font-medium mr-3 disabled:opacity-40">Verificar pago</button><button disabled={procesando===c.id} onClick={()=>marcar(c,"NO_PAGO")} className="text-red-600 font-medium disabled:opacity-40">No pago</button></td></tr>)}{!filtrados.length&&<tr><td colSpan="8" className="p-8 text-center text-gray-400">Sin casos para este filtro.</td></tr>}</tbody></table></div>
    </>}
    <ClienteDetalleModal ventaId={detalle} onClose={()=>setDetalle(null)} />
  </Layout>;
}
