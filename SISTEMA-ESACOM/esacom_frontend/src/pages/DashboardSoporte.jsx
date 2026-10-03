import { useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import {
  activarUsuario,
  crearUsuario,
  desactivarUsuario,
  editarUsuario,
  fetchAuditoria,
  fetchResumenUsuarios,
  fetchUsuarios,
  fetchDotacion,
  resetPassword,
  sincronizarGoogleSheets,
  fetchMetasKpiCalidad,
  crearMetaKpiCalidad,
} from "../api/soporte";

const ROLES = ["GERENCIA", "OPERACIONES", "CONTABILIDAD", "SUPERVISOR", "EJECUTIVO", "SOPORTE"];
const VACIO = {
  rut: "",
  nombre: "",
  correo: "",
  cargo: "EJECUTIVO",
  supervisor_id: "",
  equipo: "",
  telefono: "",
  codigo_fijo: "",
  codigo_andes: "",
  tipo_kpi: "REGULAR",
  password: "",
  is_active: true,
};

function resultados(data) {
  return Array.isArray(data) ? data : data?.results || [];
}

function Badge({ children, tipo = "gris" }) {
  const clases = {
    verde: "bg-green-50 text-green-700 border-green-200",
    rojo: "bg-red-50 text-red-700 border-red-200",
    azul: "bg-blue-50 text-blue-700 border-blue-200",
    amarillo: "bg-amber-50 text-amber-700 border-amber-200",
    gris: "bg-gray-50 text-gray-600 border-gray-200",
  };
  return <span className={`inline-flex px-2 py-0.5 rounded-full border text-[11px] font-medium ${clases[tipo]}`}>{children}</span>;
}

function ModalUsuario({ abierto, usuario, supervisores, onCerrar, onGuardado }) {
  const [form, setForm] = useState(VACIO);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!abierto) return;
    setError("");
    setForm(usuario ? {
      rut: usuario.rut || "",
      nombre: usuario.nombre || "",
      correo: usuario.correo || "",
      cargo: usuario.cargo || "EJECUTIVO",
      supervisor_id: usuario.supervisor?.id || "",
      equipo: usuario.equipo || "",
      telefono: usuario.telefono || "",
      codigo_fijo: usuario.codigo_fijo || "",
      codigo_andes: usuario.codigo_andes || "",
      tipo_kpi: usuario.tipo_kpi || "REGULAR",
      password: "",
      is_active: usuario.is_active,
    } : VACIO);
  }, [abierto, usuario]);

  if (!abierto) return null;

  function set(campo, valor) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
  }

  async function guardar(e) {
    e.preventDefault();
    setGuardando(true);
    setError("");
    try {
      const payload = {
        ...form,
        supervisor_id: form.cargo === "EJECUTIVO" && form.supervisor_id ? Number(form.supervisor_id) : null,
      };
      if (usuario && !payload.password) delete payload.password;
      if (usuario) await editarUsuario(usuario.id, payload);
      else await crearUsuario(payload);
      onGuardado();
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === "object") {
        const msg = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`).join(" · ");
        setError(msg || "No se pudo guardar el usuario.");
      } else setError("No se pudo guardar el usuario.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/35 flex items-center justify-center p-4" onMouseDown={onCerrar}>
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-2xl max-h-[92vh] overflow-y-auto" onMouseDown={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div><h2 className="font-semibold text-gray-900">{usuario ? "Editar usuario" : "Nuevo usuario"}</h2><p className="text-xs text-gray-400">Acceso y relación con la estructura ESACOM.</p></div>
          <button type="button" onClick={onCerrar} className="text-gray-400 hover:text-gray-700">✕</button>
        </div>
        <form onSubmit={guardar} className="p-6 space-y-5">
          {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{error}</div>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Campo label="RUT *"><input required value={form.rut} onChange={(e) => set("rut", e.target.value)} placeholder="19.784.357-8" className="input-soporte" /></Campo>
            <Campo label="Nombre *"><input required value={form.nombre} onChange={(e) => set("nombre", e.target.value)} className="input-soporte" /></Campo>
            <Campo label="Correo"><input type="email" value={form.correo} onChange={(e) => set("correo", e.target.value)} placeholder="usuario@esacomspa.cl" className="input-soporte" /></Campo>
            <Campo label="Rol *"><select value={form.cargo} onChange={(e) => set("cargo", e.target.value)} className="input-soporte bg-white">{ROLES.map((r) => <option key={r}>{r}</option>)}</select></Campo>
            {form.cargo === "EJECUTIVO" && <Campo label="Supervisor"><select value={form.supervisor_id} onChange={(e) => set("supervisor_id", e.target.value)} className="input-soporte bg-white"><option value="">Sin supervisor</option>{supervisores.map((s) => <option key={s.id} value={s.id}>{s.nombre} · {s.rut}</option>)}</select></Campo>}
            {form.cargo === "EJECUTIVO" && <Campo label="Perfil KPI"><select value={form.tipo_kpi} onChange={(e) => set("tipo_kpi", e.target.value)} className="input-soporte bg-white"><option value="REGULAR">Regular</option><option value="HONORARIOS">Honorarios</option></select></Campo>}
            <Campo label="Equipo"><input value={form.equipo} onChange={(e) => set("equipo", e.target.value)} className="input-soporte" /></Campo>
            <Campo label="Teléfono"><input value={form.telefono} onChange={(e) => set("telefono", e.target.value)} className="input-soporte" /></Campo>
            <Campo label="Código CE / fijo"><input value={form.codigo_fijo} onChange={(e) => set("codigo_fijo", e.target.value)} className="input-soporte" /></Campo>
            <Campo label="Código Andes"><input value={form.codigo_andes} onChange={(e) => set("codigo_andes", e.target.value)} className="input-soporte" /></Campo>
            <Campo label={usuario ? "Nueva contraseña (opcional)" : "Contraseña temporal *"}><input type="password" minLength={8} required={!usuario} value={form.password} onChange={(e) => set("password", e.target.value)} className="input-soporte" placeholder="Mínimo 8 caracteres" /></Campo>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Cuenta activa</label>
          <div className="flex justify-end gap-2 pt-2"><button type="button" onClick={onCerrar} className="px-4 py-2 rounded-lg border border-gray-300 text-sm">Cancelar</button><button disabled={guardando} className="px-4 py-2 rounded-lg bg-esacom-red text-white text-sm font-semibold disabled:opacity-60">{guardando ? "Guardando..." : "Guardar usuario"}</button></div>
        </form>
      </div>
    </div>
  );
}

function Campo({ label, children }) {
  return <label className="block"><span className="block text-xs font-medium text-gray-500 mb-1">{label}</span>{children}</label>;
}


function MetasKpiPanel() {
  const [metas, setMetas] = useState([]);
  const [form, setForm] = useState({ vigente_desde: "", meta_b1: "85.00", meta_b2: "83.00", meta_b3: "80.00", motivo: "" });
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  async function cargar() {
    setCargando(true);
    setError("");
    try {
      const data = await fetchMetasKpiCalidad();
      setMetas(resultados(data));
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudieron cargar las metas KPI.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => { cargar(); }, []);

  async function guardar(e) {
    e.preventDefault();
    if (!window.confirm(`¿Crear una nueva vigencia desde ${form.vigente_desde}? Las vigencias anteriores no se modificarán.`)) return;
    setGuardando(true);
    setError("");
    setOk("");
    try {
      await crearMetaKpiCalidad(form);
      setOk("Nueva vigencia KPI Calidad creada. El histórico anterior permanece intacto.");
      setForm((prev) => ({ ...prev, vigente_desde: "", motivo: "" }));
      await cargar();
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === "object") {
        const msg = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : v}`).join(" · ");
        setError(msg || "No se pudo crear la vigencia.");
      } else setError("No se pudo crear la vigencia.");
    } finally {
      setGuardando(false);
    }
  }

  const vigente = metas[0];
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        <b>Solo Soporte puede administrar estas metas.</b> Cada cambio crea una nueva vigencia por camada mensual; no se editan ni eliminan vigencias anteriores para evitar cambios retroactivos en meses cerrados.
      </div>
      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {ok && <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{ok}</div>}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.3fr]">
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <p className="text-xs font-bold uppercase tracking-wide text-gray-400">Meta vigente más reciente</p>
          {cargando ? <div className="mt-4 h-28 animate-pulse rounded-xl bg-gray-100" /> : vigente ? (
            <>
              <p className="mt-2 text-lg font-bold text-gray-900">Desde {vigente.vigente_desde}</p>
              <p className="mt-1 text-xs text-gray-500">Las metas se aplican por camada mensual; no reescriben meses anteriores.</p>
              <div className="mt-4 grid grid-cols-3 gap-2">
                {[["B1", vigente.meta_b1], ["B2", vigente.meta_b2], ["B3", vigente.meta_b3]].map(([b, v]) => <div key={b} className="rounded-xl bg-esacom-lime-light p-3 text-center"><p className="text-[10px] font-bold text-gray-500">{b}</p><p className="text-xl font-extrabold text-esacom-ink">{Number(v).toFixed(0)}%</p></div>)}
              </div>
              <p className="mt-3 text-xs text-gray-500">{vigente.motivo}</p>
            </>
          ) : <p className="mt-3 text-sm text-gray-400">No hay vigencias configuradas.</p>}
        </div>

        <form onSubmit={guardar} className="rounded-xl border border-gray-200 bg-white p-5">
          <div><h2 className="text-sm font-bold text-gray-900">Crear nueva vigencia</h2><p className="mt-1 text-xs text-gray-500">Úsalo solo cuando Gerencia confirme un cambio. La fecha indica la camada desde la que empieza a aplicar.</p></div>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
            <Campo label="Vigente desde *"><input required type="month" value={form.vigente_desde} onChange={(e) => setForm({ ...form, vigente_desde: e.target.value })} className="input-soporte" /></Campo>
            <Campo label="Meta B1 (%) *"><input required type="number" min="0" max="100" step="0.01" value={form.meta_b1} onChange={(e) => setForm({ ...form, meta_b1: e.target.value })} className="input-soporte" /></Campo>
            <Campo label="Meta B2 (%) *"><input required type="number" min="0" max="100" step="0.01" value={form.meta_b2} onChange={(e) => setForm({ ...form, meta_b2: e.target.value })} className="input-soporte" /></Campo>
            <Campo label="Meta B3 (%) *"><input required type="number" min="0" max="100" step="0.01" value={form.meta_b3} onChange={(e) => setForm({ ...form, meta_b3: e.target.value })} className="input-soporte" /></Campo>
          </div>
          <Campo label="Motivo / respaldo de Gerencia *"><input required minLength={5} value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })} placeholder="Ej.: Meta confirmada por Gerencia para nueva vigencia" className="input-soporte mt-1" /></Campo>
          <div className="mt-4 flex justify-end"><button disabled={guardando} className="rounded-lg bg-esacom-red px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? "Guardando…" : "Crear vigencia"}</button></div>
        </form>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        <div className="border-b border-gray-100 p-4"><h2 className="text-sm font-semibold">Histórico de metas KPI Calidad</h2><p className="mt-1 text-xs text-gray-400">Registro inmutable de las metas ESACOM utilizadas por cada camada.</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-xs"><thead><tr className="bg-gray-50 text-gray-500"><th className="px-4 py-3 text-left">Vigente desde</th><th className="px-3 py-3 text-right">B1</th><th className="px-3 py-3 text-right">B2</th><th className="px-3 py-3 text-right">B3</th><th className="px-3 py-3 text-left">Motivo</th><th className="px-4 py-3 text-left">Creado por</th></tr></thead><tbody>{metas.map((m) => <tr key={m.id} className="border-t border-gray-100"><td className="px-4 py-3 font-semibold">{m.vigente_desde}</td><td className="px-3 py-3 text-right">{Number(m.meta_b1).toFixed(2)}%</td><td className="px-3 py-3 text-right">{Number(m.meta_b2).toFixed(2)}%</td><td className="px-3 py-3 text-right">{Number(m.meta_b3).toFixed(2)}%</td><td className="px-3 py-3 text-gray-600">{m.motivo}</td><td className="px-4 py-3 text-gray-500">{m.creado_por_nombre || "Sistema"}</td></tr>)}</tbody></table></div>
        {!cargando && metas.length === 0 && <p className="p-6 text-center text-sm text-gray-400">Sin vigencias registradas.</p>}
      </div>
    </div>
  );
}

export default function DashboardSoporte() {
  const { user } = useAuth();
  const [usuarios, setUsuarios] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [auditoria, setAuditoria] = useState([]);
  const [dotacion, setDotacion] = useState({ resumen: null, filas: [] });
  const [supervisores, setSupervisores] = useState([]);
  const [q, setQ] = useState("");
  const [cargo, setCargo] = useState("");
  const [estado, setEstado] = useState("");
  const [tipoKpi, setTipoKpi] = useState("");
  const [tab, setTab] = useState("usuarios");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState({ abierto: false, usuario: null });
  const [mensaje, setMensaje] = useState("");
  const [sincronizandoEsacom, setSincronizandoEsacom] = useState(false);
  const [ultimaSyncManual, setUltimaSyncManual] = useState(null);
  const primeraBusqueda = useRef(true);

  async function cargarTodo(parametros = {}) {
    setCargando(true);
    setError("");
    try {
      const [u, r, a, s, d] = await Promise.all([
        fetchUsuarios({ q, cargo, estado, tipo_kpi: tipoKpi, ...parametros }),
        fetchResumenUsuarios(),
        fetchAuditoria(),
        fetchUsuarios({ cargo: "SUPERVISOR", estado: "activo" }),
        fetchDotacion({ q, estado, tipo_kpi: tipoKpi, ...parametros }),
      ]);
      setUsuarios(resultados(u));
      setResumen(r);
      setAuditoria(resultados(a));
      setSupervisores(resultados(s));
      setDotacion(d || { resumen: null, filas: [] });
    } catch {
      setError("No se pudo cargar la administración de usuarios.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => { cargarTodo(); }, [cargo, estado, tipoKpi]);

  // Búsqueda en vivo con un pequeño debounce para no disparar una petición por tecla.
  useEffect(() => {
    if (primeraBusqueda.current) {
      primeraBusqueda.current = false;
      return;
    }
    const timer = window.setTimeout(() => cargarTodo({ q }), 280);
    return () => window.clearTimeout(timer);
  }, [q]);

  async function buscar(e) { e.preventDefault(); await cargarTodo({ q }); }

  function limpiarBusqueda() { setQ(""); }

  async function cambiarEstado(usuario) {
    if (usuario.id === user?.id && usuario.is_active) return setMensaje("No puedes desactivar tu propia cuenta.");
    try {
      if (usuario.is_active) await desactivarUsuario(usuario.id); else await activarUsuario(usuario.id);
      setMensaje(usuario.is_active ? "Usuario desactivado." : "Usuario activado.");
      await cargarTodo();
    } catch (err) { setMensaje(err.response?.data?.detail || "No se pudo cambiar el estado."); }
  }

  async function sincronizarEsacomAhora() {
    if (!window.confirm("¿Sincronizar ahora la fuente maestra ESACOM desde Google Sheets? El KPI Claro no se modifica.")) return;
    setSincronizandoEsacom(true);
    setError("");
    setMensaje("");
    try {
      const r = await sincronizarGoogleSheets();
      const ventas = r?.resumen?.base_ventas?.ventas_creadas ?? r?.ventas_creadas;
      setMensaje(`Sincronización ESACOM aplicada${ventas !== undefined ? ` · ventas nuevas: ${ventas}` : ""}. KPI Claro sin cambios.`);
      setUltimaSyncManual(new Date());
      await cargarTodo();
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo sincronizar Google Sheets ESACOM.");
    } finally {
      setSincronizandoEsacom(false);
    }
  }

  async function restablecer(usuario) {
    if (!window.confirm(`¿Restablecer la contraseña de ${usuario.nombre}?`)) return;
    try {
      const r = await resetPassword(usuario.id);
      const texto = r.password_temporal ? `Contraseña temporal: ${r.password_temporal}` : r.detail;
      setMensaje(texto);
      await cargarTodo();
    } catch { setMensaje("No se pudo restablecer la contraseña."); }
  }

  return (
    <Layout titulo="Dashboard Soporte" items={[{ label: "Usuarios", to: "/soporte" }, { label: "Permisos", to: "/permisos" }] }>
      {mensaje && <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 flex justify-between gap-3"><span className="font-medium break-all">{mensaje}</span><button onClick={() => setMensaje("")}>✕</button></div>}
      {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="mb-4 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-blue-900">Fuente maestra ESACOM · Google Sheets</p>
          <p className="text-xs text-blue-700 mt-1">Sincroniza ventas, clientes, dotación y estados operacionales. El KPI Claro se mantiene como carga manual independiente.</p>
          {ultimaSyncManual && <p className="text-[11px] text-blue-600 mt-1">Última sincronización solicitada desde esta pantalla: {ultimaSyncManual.toLocaleString("es-CL")}</p>}
        </div>
        <button type="button" onClick={sincronizarEsacomAhora} disabled={sincronizandoEsacom} className="min-h-11 rounded-xl bg-blue-700 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50 shrink-0">
          {sincronizandoEsacom ? "Sincronizando…" : "↻ Sincronizar ahora con ESACOM"}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-9 gap-3 mb-6">
        {resumen ? [
          ["Usuarios", resumen.total], ["Activos", resumen.activos], ["Ejecutivos", resumen.ejecutivos],
          ["Honorarios", resumen.honorarios], ["Supervisores", resumen.supervisores], ["Operaciones", resumen.operaciones], ["Contabilidad", resumen.contabilidad], ["Gerencia", resumen.gerencia], ["Soporte", resumen.soporte],
        ].map(([l, v]) => <div key={l} className="bg-white border border-gray-200 rounded-xl p-4"><p className="text-2xl font-bold text-gray-900">{v}</p><p className="text-xs text-gray-500 mt-1">{l}</p></div>) : Array.from({ length: 9 }).map((_, i) => <div key={i} className="h-20 bg-gray-100 animate-pulse rounded-xl" />)}
      </div>

      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
        <button onClick={() => setTab("usuarios")} className={`px-4 py-2 rounded-lg text-sm ${tab === "usuarios" ? "bg-white shadow-sm font-semibold" : "text-gray-500"}`}>Gestión de usuarios</button>
        <button onClick={() => setTab("auditoria")} className={`px-4 py-2 rounded-lg text-sm ${tab === "auditoria" ? "bg-white shadow-sm font-semibold" : "text-gray-500"}`}>Auditoría</button>
        <button onClick={() => setTab("dotacion")} className={`px-4 py-2 rounded-lg text-sm ${tab === "dotacion" ? "bg-white shadow-sm font-semibold" : "text-gray-500"}`}>Dotación y asignaciones</button>
        <button onClick={() => setTab("metas")} className={`px-4 py-2 rounded-lg text-sm ${tab === "metas" ? "bg-white shadow-sm font-semibold" : "text-gray-500"}`}>Metas KPI</button>
      </div>

      {tab === "metas" ? <MetasKpiPanel /> : tab === "dotacion" ? <div className="space-y-4">
        <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <b>Fuente: Dotación ESACOM.</b> El rol de acceso CRM se administra por separado del cargo laboral. Las asignaciones se resuelven por catálogo controlado y RUT, nunca por coincidencia parcial de nombres.
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {[
            ["Personas", dotacion.resumen?.personas ?? 0], ["Activos", dotacion.resumen?.activos ?? 0],
            ["Inactivos", dotacion.resumen?.inactivos ?? 0], ["Honorarios", dotacion.resumen?.honorarios ?? 0],
            ["Supervisores CRM", dotacion.resumen?.supervisores_crm ?? 0], ["Sin supervisor", dotacion.resumen?.sin_supervisor ?? 0],
          ].map(([l,v]) => <div key={l} className="bg-white border border-gray-200 rounded-xl p-4"><p className="text-2xl font-bold">{v}</p><p className="text-xs text-gray-500 mt-1">{l}</p></div>)}
        </div>
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-gray-100"><h2 className="text-sm font-semibold">Asignación Ejecutivo → Supervisor</h2><p className="text-xs text-gray-400 mt-1">Permite responder quién está asignado a quién y detectar inconsistencias de la fuente.</p></div>
          <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="bg-gray-50 text-gray-500"><th className="text-left px-4 py-3">Persona</th><th className="text-left px-3 py-3">Rol CRM / Cargo ESACOM</th><th className="text-left px-3 py-3">Tipo / Estado</th><th className="text-left px-3 py-3">Supervisor fuente</th><th className="text-left px-3 py-3">Supervisor resuelto</th><th className="text-left px-3 py-3">Última sync</th></tr></thead><tbody>
            {(dotacion.filas || []).map((u) => <tr key={u.id} className="border-t border-gray-100"><td className="px-4 py-3"><p className="font-semibold">{u.nombre}</p><p className="text-gray-400">{u.rut}</p></td><td className="px-3 py-3"><Badge tipo={u.rol_crm === "SUPERVISOR" ? "amarillo" : "gris"}>{u.rol_crm}</Badge><p className="text-gray-400 mt-1">{u.cargo_fuente || "—"}</p></td><td className="px-3 py-3"><Badge tipo={u.tipo_kpi === "HONORARIOS" ? "amarillo" : "gris"}>{u.tipo_kpi}</Badge><div className="mt-1"><Badge tipo={u.estado === "ACTIVO" ? "verde" : "rojo"}>{u.estado}</Badge></div><p className="text-gray-400 mt-1">{u.estado_fuente || "—"}</p></td><td className="px-3 py-3">{u.supervisor_fuente || "—"}</td><td className="px-3 py-3">{u.supervisor ? <><p className="font-medium">{u.supervisor.nombre}</p><p className="text-gray-400">{u.supervisor.rut}</p></> : <Badge tipo="rojo">SIN RESOLVER</Badge>}</td><td className="px-3 py-3 text-gray-500">{u.ultima_sync ? new Date(u.ultima_sync).toLocaleString("es-CL") : "—"}</td></tr>)}
          </tbody></table></div>
        </div>
      </div> : tab === "usuarios" ? <>
        <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 flex flex-col lg:flex-row gap-3 lg:items-end">
          <form onSubmit={buscar} className="flex-1 flex gap-2">
            <div className="relative flex-1">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Escape") limpiarBusqueda(); }}
                placeholder="Buscar nombre, RUT, supervisor, equipo, correo o código..."
                className="input-soporte w-full pr-9"
                autoComplete="off"
              />
              {q && <button type="button" onClick={limpiarBusqueda} aria-label="Limpiar búsqueda" className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 px-1">✕</button>}
            </div>
            <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium">Buscar</button>
          </form>
          <select value={cargo} onChange={(e) => setCargo(e.target.value)} className="input-soporte bg-white lg:w-44"><option value="">Todos los roles</option>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} className="input-soporte bg-white lg:w-40"><option value="">Todos</option><option value="activo">Activos</option><option value="inactivo">Inactivos</option></select>
          <select value={tipoKpi} onChange={(e) => setTipoKpi(e.target.value)} className="input-soporte bg-white lg:w-40"><option value="">Todos KPI</option><option value="REGULAR">Regular</option><option value="HONORARIOS">Honorarios</option></select>
          <button onClick={() => setModal({ abierto: true, usuario: null })} className="px-4 py-2 rounded-lg bg-esacom-red text-white text-sm font-semibold whitespace-nowrap">+ Crear usuario</button>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="bg-gray-50 text-gray-500"><th className="text-left px-4 py-3">Usuario</th><th className="text-left px-3 py-3">Rol / KPI</th><th className="text-left px-3 py-3">Supervisor / Equipo</th><th className="text-left px-3 py-3">Estado</th><th className="text-left px-3 py-3">Último acceso</th><th className="text-right px-4 py-3">Acciones</th></tr></thead><tbody>
            {usuarios.map((u) => <tr key={u.id} className="border-t border-gray-100 hover:bg-gray-50/50"><td className="px-4 py-3"><p className="font-semibold text-gray-800">{u.nombre}</p><p className="text-gray-400">{u.rut}{u.correo ? ` · ${u.correo}` : ""}</p></td><td className="px-3 py-3"><Badge tipo={u.cargo === "SOPORTE" ? "azul" : u.cargo === "GERENCIA" ? "rojo" : u.cargo === "SUPERVISOR" ? "amarillo" : "gris"}>{u.cargo}</Badge>{u.cargo === "EJECUTIVO" && <div className="mt-1"><Badge tipo={u.tipo_kpi === "HONORARIOS" ? "amarillo" : "gris"}>{u.tipo_kpi || "REGULAR"}</Badge></div>}</td><td className="px-3 py-3 text-gray-600"><p>{u.supervisor?.nombre || "—"}</p><p className="text-gray-400">{u.equipo || "Sin equipo"}</p></td><td className="px-3 py-3"><Badge tipo={u.is_active ? "verde" : "rojo"}>{u.is_active ? "Activo" : "Inactivo"}</Badge></td><td className="px-3 py-3 text-gray-500">{u.ultimo_acceso ? new Date(u.ultimo_acceso).toLocaleString("es-CL") : "Nunca"}</td><td className="px-4 py-3"><div className="flex justify-end gap-1"><button onClick={() => setModal({ abierto: true, usuario: u })} className="px-2 py-1.5 rounded border border-gray-200 hover:border-gray-400">Editar</button><button onClick={() => restablecer(u)} className="px-2 py-1.5 rounded border border-gray-200 hover:border-blue-300 text-blue-700">Reset clave</button><button onClick={() => cambiarEstado(u)} disabled={u.id === user?.id && u.is_active} className={`px-2 py-1.5 rounded border disabled:opacity-40 ${u.is_active ? "border-red-200 text-red-700" : "border-green-200 text-green-700"}`}>{u.is_active ? "Desactivar" : "Activar"}</button></div></td></tr>)}
          </tbody></table></div>
          {!cargando && usuarios.length === 0 && <p className="p-8 text-center text-sm text-gray-400">No hay usuarios para estos filtros.</p>}
          {cargando && <p className="p-8 text-center text-sm text-gray-400">Cargando usuarios...</p>}
        </div>
      </> : <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-100"><h2 className="text-sm font-semibold">Auditoría de accesos</h2><p className="text-xs text-gray-400 mt-1">Registro de altas, cambios de usuario, activaciones y restablecimientos de contraseña.</p></div>
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="bg-gray-50 text-gray-500"><th className="text-left px-4 py-3">Fecha</th><th className="text-left px-3 py-3">Acción</th><th className="text-left px-3 py-3">Realizado por</th><th className="text-left px-4 py-3">Usuario afectado</th></tr></thead><tbody>{auditoria.map((a) => <tr key={a.id} className="border-t border-gray-100"><td className="px-4 py-3 text-gray-500">{new Date(a.creado_en).toLocaleString("es-CL")}</td><td className="px-3 py-3"><Badge tipo="azul">{a.accion}</Badge></td><td className="px-3 py-3"><p className="font-medium">{a.actor_nombre || "Sistema"}</p><p className="text-gray-400">{a.actor_rut || "—"}</p></td><td className="px-4 py-3"><p className="font-medium">{a.objetivo_nombre || "—"}</p><p className="text-gray-400">{a.objetivo_rut || "—"}</p></td></tr>)}</tbody></table></div>
        {auditoria.length === 0 && <p className="p-8 text-center text-sm text-gray-400">Todavía no hay acciones de Soporte registradas.</p>}
      </div>}

      <ModalUsuario abierto={modal.abierto} usuario={modal.usuario} supervisores={supervisores} onCerrar={() => setModal({ abierto: false, usuario: null })} onGuardado={async () => { setModal({ abierto: false, usuario: null }); setMensaje("Usuario guardado correctamente."); await cargarTodo(); }} />
    </Layout>
  );
}
