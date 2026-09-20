import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [rut, setRut] = useState("");
  const [password, setPassword] = useState("");
  const [mostrarPassword, setMostrarPassword] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault(); setError(""); setEnviando(true);
    try { const me = await login(rut, password); navigate(rutaPorCargo(me.cargo), { replace: true }); }
    catch (err) { setError(err.response?.status === 401 ? "RUT o contraseña incorrectos." : "No se pudo conectar con el servidor. Intenta de nuevo."); }
    finally { setEnviando(false); }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f5f6f7] px-4 py-8 sm:py-12 flex items-center justify-center">
      <div aria-hidden="true" className="absolute -left-24 top-20 h-72 w-72 rounded-full bg-esacom-lime/10 blur-3xl" />
      <div aria-hidden="true" className="absolute -right-24 bottom-10 h-80 w-80 rounded-full bg-gray-300/25 blur-3xl" />
      <div className="relative w-full max-w-md">
        <section className="rounded-[28px] border border-gray-200/90 bg-white p-5 shadow-[0_24px_70px_rgba(32,35,40,0.12)] sm:p-8">
          <div className="flex flex-col items-center text-center">
            <img src="/esacom-logo.png" alt="ESACOM SpA" className="h-28 w-28 object-contain sm:h-32 sm:w-32" />
            <p className="mt-2 text-[11px] font-bold uppercase tracking-[0.22em] text-esacom-lime-dark">CRM Comercial</p>
            <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-esacom-ink sm:text-3xl">Bienvenido a ESACOM</h1>
            <p className="mt-2 max-w-xs text-sm leading-6 text-gray-500">Consulta tus ventas, clientes y KPI con información operativa ESACOM.</p>
          </div>
          <form onSubmit={handleSubmit} className="mt-7 space-y-5">
            <div>
              <label htmlFor="rut" className="mb-1.5 block text-sm font-semibold text-gray-700">RUT</label>
              <input id="rut" type="text" autoComplete="username" placeholder="19.784.357-8" value={rut} onChange={(e)=>setRut(e.target.value)} required className="esacom-focus min-h-12 w-full rounded-xl border border-gray-300 bg-gray-50 px-3.5 text-base text-gray-900 placeholder:text-gray-400" />
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-3"><label htmlFor="password" className="block text-sm font-semibold text-gray-700">Contraseña</label><span className="text-xs text-gray-400">Asignada por Soporte</span></div>
              <div className="relative">
                <input id="password" type={mostrarPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e)=>setPassword(e.target.value)} required className="esacom-focus min-h-12 w-full rounded-xl border border-gray-300 bg-gray-50 px-3.5 pr-20 text-base text-gray-900" />
                <button type="button" onClick={()=>setMostrarPassword(v=>!v)} className="absolute inset-y-0 right-2 my-auto h-9 rounded-lg px-2.5 text-xs font-semibold text-gray-500 hover:bg-gray-100 hover:text-gray-800" aria-label={mostrarPassword ? "Ocultar contraseña" : "Mostrar contraseña"}>{mostrarPassword ? "Ocultar" : "Mostrar"}</button>
              </div>
            </div>
            {error && <div role="alert" className="rounded-xl border border-red-100 bg-red-50 px-3.5 py-3 text-sm font-medium text-red-700">{error}</div>}
            <button type="submit" disabled={enviando} className="esacom-primary-btn w-full text-base">{enviando ? "Ingresando…" : "Ingresar"}</button>
          </form>
          <div className="mt-6 border-t border-gray-100 pt-5 text-center"><p className="text-xs leading-5 text-gray-400">Acceso exclusivo para usuarios autorizados. Para restablecer tu clave, solicítalo a Soporte ESACOM.</p></div>
        </section>
        <p className="mt-4 text-center text-[11px] text-gray-400">ESACOM SpA · Plataforma de gestión comercial</p>
      </div>
    </main>
  );
}
export function rutaPorCargo(cargo) {
  switch (cargo) {
    case "GERENCIA": return "/dashboard"; case "OPERACIONES": return "/operaciones"; case "CONTABILIDAD": return "/contabilidad"; case "SUPERVISOR": return "/supervisor"; case "EJECUTIVO": return "/mi-portal"; case "SOPORTE": return "/soporte"; default: return "/";
  }
}
