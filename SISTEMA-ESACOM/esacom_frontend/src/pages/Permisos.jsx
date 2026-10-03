import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { configurarPermisos, fetchPermisosUsuarios, restablecerPermisos } from "../api/soporte";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

const GRUPOS = [
  ["Operación", [["mi_equipo","Mi Equipo"],["mi_portal","Mi Portal"],["accionables","Accionables"]]],
  ["Finanzas", [["cobranza","Cobranza"],["historico","Histórico"]]],
  ["Gestión y control", [["apelaciones","Apelaciones"],["analisis","Análisis"],["auditoria_kpi","Auditoría KPI"],["dashboard_gerencia","Dashboard Gerencia"]]],
  ["Datos", [["base_datos","Base de Datos"],["cargar_datos","Carga de Datos"]]],
  ["Administración", [["usuarios","Usuarios"],["permisos","Centro de Permisos"]]],
];
const NO_DELEGABLES = new Set(["usuarios","permisos","cargar_datos"]);
const SENSIBLES = new Set(["dashboard_gerencia","base_datos","cargar_datos","auditoria_kpi"]);

export default function Permisos() {
  const { user } = useAuth();
  const [usuarios,setUsuarios]=useState([]); const [q,setQ]=useState(""); const [sel,setSel]=useState(null);
  const [draft,setDraft]=useState({}); const [mensaje,setMensaje]=useState(""); const [cargando,setCargando]=useState(true);
  const [confirmando,setConfirmando]=useState(false); const [motivo,setMotivo]=useState(""); const [error,setError]=useState("");
  async function cargar(){ setCargando(true); try{ const d=await fetchPermisosUsuarios(); setUsuarios(Array.isArray(d)?d:d.results||[]);} finally{setCargando(false);} }
  useEffect(()=>{cargar();},[]);
  const filtrados=useMemo(()=>usuarios.filter(u=>`${u.nombre} ${u.rut} ${u.cargo}`.toLowerCase().includes(q.toLowerCase())),[usuarios,q]);
  function elegir(u){ setSel(u); setDraft({...u.permisos}); setMensaje(""); setError(""); setConfirmando(false); setMotivo(""); }
  const cambios=useMemo(()=>{if(!sel)return[]; return Object.keys(draft).filter(k=>!!draft[k]!==!!sel.permisos?.[k]).map(k=>({k,antes:!!sel.permisos?.[k],despues:!!draft[k]}));},[draft,sel]);
  async function guardar(){ if(!sel)return; if(!confirmando){setConfirmando(true);return;} setError(""); try{const r=await configurarPermisos(sel.id,draft,motivo); setMensaje("Permisos guardados y auditados."); setSel(r); setDraft({...r.permisos}); setConfirmando(false); setMotivo(""); await cargar();}catch(e){setError(e.response?.data?.detail||e.response?.data?.motivo?.[0]||"No se pudieron guardar los permisos.");}}
  async function reset(){ if(!sel||!confirm("¿Restablecer permisos al perfil base del rol?"))return; const r=await restablecerPermisos(sel.id); setMensaje("Permisos restablecidos al rol."); setSel(r); setDraft({...r.permisos}); await cargar(); }
  const totalActivos=Object.values(draft).filter(Boolean).length;
  return <Layout titulo="Centro de Permisos" items={menuPorUsuario(user)}>
    <div className="grid lg:grid-cols-[360px_1fr] gap-4">
      <section className="bg-white border border-gray-200 rounded-2xl overflow-hidden"><div className="p-4 border-b border-gray-100"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar usuario, RUT o rol..." className="w-full min-h-11 border border-gray-300 rounded-xl px-3 text-sm"/></div><div className="max-h-[68vh] overflow-y-auto divide-y divide-gray-100">{cargando?<p className="p-5 text-sm text-gray-400">Cargando...</p>:filtrados.map(u=><button key={u.id} onClick={()=>elegir(u)} className={`w-full text-left p-4 hover:bg-gray-50 ${sel?.id===u.id?"bg-red-50":""}`}><p className="font-semibold text-sm text-gray-900">{u.nombre}</p><p className="text-xs text-gray-400">{u.rut} · {u.cargo}</p></button>)}</div></section>
      <section className="bg-white border border-gray-200 rounded-2xl p-5">{!sel?<div className="min-h-64 flex items-center justify-center text-sm text-gray-400">Selecciona un usuario para administrar sus permisos.</div>:<>
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 border-b border-gray-100 pb-4"><div><h2 className="font-bold text-lg">{sel.nombre}</h2><p className="text-sm text-gray-500">{sel.rut} · {sel.cargo} · {sel.equipo||"Sin equipo"}</p><p className="text-xs text-gray-400 mt-1">Perfil base: <b>{sel.cargo}</b> · {totalActivos} módulos efectivos. Los permisos administrativos no son delegables.</p></div><span className={`text-xs px-3 py-1.5 rounded-full ${sel.is_active?"bg-green-50 text-green-700":"bg-red-50 text-red-700"}`}>{sel.is_active?"Activo":"Inactivo"}</span></div>
        {mensaje&&<div className="mt-4 rounded-xl bg-blue-50 text-blue-700 px-4 py-3 text-sm">{mensaje}</div>}{error&&<div className="mt-4 rounded-xl bg-red-50 text-red-700 px-4 py-3 text-sm">{error}</div>}
        <div className="space-y-5 mt-5">{GRUPOS.map(([grupo,mods])=><div key={grupo}><p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">{grupo}</p><div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">{mods.map(([k,label])=>{const bloqueado=NO_DELEGABLES.has(k); return <label key={k} className={`flex items-center justify-between gap-3 border rounded-xl px-4 py-3 ${bloqueado?"bg-gray-50 border-gray-200":"border-gray-200 hover:border-gray-300"}`}><span><span className="flex items-center gap-2 text-sm font-medium">{label}{SENSIBLES.has(k)&&<span className="text-[10px] rounded-full bg-amber-50 text-amber-700 px-2 py-0.5">Sensible</span>}{bloqueado&&<span className="text-[10px] rounded-full bg-gray-200 text-gray-600 px-2 py-0.5">Por rol</span>}</span><span className="text-[11px] text-gray-400">Base: {sel.permisos_base?.[k]?"Permitido":"Bloqueado"}</span></span><input disabled={bloqueado} type="checkbox" checked={!!draft[k]} onChange={e=>setDraft({...draft,[k]:e.target.checked})} className="h-5 w-5 accent-red-600 disabled:opacity-40"/></label>})}</div></div>)}</div>
        {confirmando&&<div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="font-semibold text-sm text-gray-900">Confirmar cambios</p>{cambios.length?<ul className="mt-2 text-xs text-gray-700 space-y-1">{cambios.map(c=><li key={c.k}>{c.despues?"+ Habilitar":"- Bloquear"}: <b>{c.k}</b></li>)}</ul>:<p className="text-xs text-gray-500 mt-2">No hay diferencias respecto a los permisos actuales.</p>}<label className="block mt-3 text-xs font-semibold text-gray-700">Motivo del cambio</label><textarea value={motivo} onChange={e=>setMotivo(e.target.value)} rows="2" placeholder="Ej.: reemplazo temporal, función operacional, ajuste aprobado por Gerencia..." className="mt-1 w-full rounded-xl border border-gray-300 bg-white p-3 text-sm"/></div>}
        <div className="flex flex-col sm:flex-row justify-end gap-2 mt-6"><button onClick={reset} className="min-h-11 px-4 rounded-xl border border-gray-300 text-sm font-semibold">Restablecer rol</button>{confirmando&&<button onClick={()=>setConfirmando(false)} className="min-h-11 px-4 rounded-xl border border-gray-300 text-sm font-semibold">Cancelar</button>}<button onClick={guardar} disabled={confirmando&&motivo.trim().length<5} className="min-h-11 px-5 rounded-xl bg-esacom-red text-white text-sm font-semibold disabled:opacity-40">{confirmando?"Confirmar cambios":"Guardar permisos"}</button></div>
      </>}</section>
    </div>
  </Layout>;
}
