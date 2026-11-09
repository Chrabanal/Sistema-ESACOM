import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import { auditarRRHHArchivo, auditarRRHHConfigurado } from "../api/rrhh";

function Badge({ children, tipo = "gris" }) {
  const clases = {
    gris: "border-gray-200 bg-gray-50 text-gray-600",
    verde: "border-green-200 bg-green-50 text-green-700",
    amarillo: "border-amber-200 bg-amber-50 text-amber-700",
    rojo: "border-red-200 bg-red-50 text-red-700",
    azul: "border-blue-200 bg-blue-50 text-blue-700",
  };
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${clases[tipo]}`}>{children}</span>;
}

function Tarjeta({ label, value, nota }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-2xl font-extrabold text-esacom-ink">{value ?? 0}</p>
      <p className="mt-1 text-xs font-semibold text-gray-600">{label}</p>
      {nota && <p className="mt-1 text-[11px] text-gray-400">{nota}</p>}
    </div>
  );
}

export default function AuditoriaRRHH() {
  const [archivo, setArchivo] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("TODAS");

  const filas = useMemo(() => {
    const base = resultado?.filas || [];
    if (filtro === "ALTA") {
      return base.filter((fila) => fila.diferencias?.some((d) => d.severidad === "ALTA"));
    }
    if (filtro === "SUPERVISOR") {
      return base.filter((fila) => fila.diferencias?.some((d) => d.campo.includes("supervisor")));
    }
    return base;
  }, [resultado, filtro]);

  async function ejecutar(fn) {
    setCargando(true);
    setError("");
    try {
      setResultado(await fn());
    } catch (err) {
      setResultado(null);
      setError(err.response?.data?.detail || "No se pudo analizar Recursos Humanos.");
    } finally {
      setCargando(false);
    }
  }

  const r = resultado?.resumen || {};

  return (
    <Layout titulo="Auditoría Recursos Humanos">
      <div className="space-y-5">
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
          <p className="font-bold">R2.13 · Comparación segura en modo DRY-RUN</p>
          <p className="mt-1 text-xs leading-5">
            RRHH se compara por RUT contra el CRM. Esta pantalla no crea, edita, activa ni desactiva usuarios.
            El rol CRM y las contraseñas quedan protegidos. Columnas privadas como CLAVE ANDES, dirección,
            nacimiento, AFP y salud no se importan.
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-600">Probar con un archivo RRHH (.xlsx)</label>
              <input
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(e) => setArchivo(e.target.files?.[0] || null)}
                className="block w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm"
              />
              <p className="mt-1 text-[11px] text-gray-400">El archivo se analiza temporalmente y no se guarda en el CRM.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                disabled={!archivo || cargando}
                onClick={() => ejecutar(() => auditarRRHHArchivo(archivo))}
                className="min-h-10 rounded-xl bg-esacom-red px-4 text-sm font-semibold text-white disabled:opacity-40"
              >
                {cargando ? "Analizando..." : "Analizar XLSX"}
              </button>
              <button
                disabled={cargando}
                onClick={() => ejecutar(auditarRRHHConfigurado)}
                className="min-h-10 rounded-xl border border-gray-300 bg-white px-4 text-sm font-semibold text-gray-700 disabled:opacity-40"
              >
                Fuente configurada
              </button>
            </div>
          </div>
          {error && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>}
        </div>

        {resultado && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
              <Badge tipo="azul">{resultado.fuente?.modo}</Badge>
              <span className="font-semibold text-gray-700">{resultado.fuente?.nombre}</span>
              <span>·</span>
              <span>Solo lectura</span>
              <span>·</span>
              <span>Roles CRM protegidos</span>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
              <Tarjeta label="RUT RRHH" value={r.ruts_unicos} nota="histórico completo" />
              <Tarjeta label="Vigentes RRHH" value={r.rrhh_vigentes} nota="activo/honorario/pendiente" />
              <Tarjeta label="Comerciales" value={r.rrhh_comerciales_vigentes} />
              <Tarjeta label="Honorarios" value={r.rrhh_honorarios_vigentes} />
              <Tarjeta label="Coinciden RUT" value={r.coincidencias_por_rut} />
              <Tarjeta label="Solo RRHH" value={r.solo_rrhh} />
              <Tarjeta label="Con diferencias" value={r.con_diferencias} />
              <Tarjeta label="Sup. no resueltos" value={r.supervisores_no_resueltos} />
            </div>

            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <div className="flex flex-col gap-3 border-b border-gray-100 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-bold text-gray-900">Diferencias RRHH ↔ CRM</h2>
                  <p className="mt-1 text-xs text-gray-400">Son propuestas de revisión; ninguna se aplica automáticamente.</p>
                </div>
                <div className="flex gap-1 rounded-xl bg-gray-100 p-1">
                  {[['TODAS','Todas'],['ALTA','Prioridad alta'],['SUPERVISOR','Supervisores']].map(([v,l]) => (
                    <button key={v} onClick={() => setFiltro(v)} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${filtro === v ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'}`}>{l}</button>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px] text-xs">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500">
                      <th className="px-4 py-3 text-left">Persona</th>
                      <th className="px-3 py-3 text-left">RRHH</th>
                      <th className="px-3 py-3 text-left">Campo</th>
                      <th className="px-3 py-3 text-left">CRM actual</th>
                      <th className="px-3 py-3 text-left">RRHH propone</th>
                      <th className="px-4 py-3 text-left">Revisión sugerida</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filas.flatMap((fila) => (fila.diferencias || []).map((d, idx) => (
                      <tr key={`${fila.rut}-${d.campo}-${idx}`} className="border-t border-gray-100 align-top">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-gray-800">{fila.nombre}</p>
                          <p className="text-gray-400">{fila.rut}</p>
                          {fila.rol_crm && <div className="mt-1"><Badge>{fila.rol_crm} · protegido</Badge></div>}
                        </td>
                        <td className="px-3 py-3 text-gray-600">
                          <p>{fila.estado_trabajador_rrhh || '—'} · {fila.tipo_contrato_rrhh || '—'}</p>
                          <p className="mt-1 text-gray-400">{fila.supervisor_rrhh || 'Sin supervisor'} · {fila.plaza_rrhh || 'Sin plaza'}</p>
                        </td>
                        <td className="px-3 py-3"><Badge tipo={d.severidad === 'ALTA' ? 'rojo' : 'amarillo'}>{d.campo}</Badge></td>
                        <td className="px-3 py-3 text-gray-600">{String(d.crm ?? '—')}</td>
                        <td className="px-3 py-3 font-semibold text-gray-800">{String(d.rrhh ?? '—')}</td>
                        <td className="px-4 py-3 text-gray-500">{d.accion_sugerida}</td>
                      </tr>
                    )))}
                  </tbody>
                </table>
              </div>
              {filas.length === 0 && <p className="p-8 text-center text-sm text-gray-400">No hay diferencias para este filtro.</p>}
            </div>

            {r.ruts_duplicados?.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
                <b>Atención:</b> RRHH contiene RUT repetidos: {r.ruts_duplicados.join(', ')}. La auditoría usa la última fila y exige revisión manual.
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
