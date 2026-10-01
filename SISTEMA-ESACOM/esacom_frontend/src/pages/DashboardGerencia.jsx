import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import KpiCard from "../components/KpiCard";
import { ADMIN_URL } from "../api/client";
import { fetchDashboardGerencia } from "../api/dashboard";

const BOLETA_NOMBRE = { B1: "1ª Boleta", B2: "2ª Boleta", B3: "3ª Boleta" };
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

function nombreMes(valor) {
  if (!valor || !valor.includes("-")) return valor || "—";
  const [anio, mes] = valor.split("-");
  return `${MESES[Number(mes) - 1]} ${anio}`;
}

function porcentaje(valor) {
  return `${Number(valor || 0).toFixed(2)}%`;
}

function Semaforo({ valor, meta }) {
  const color = valor >= meta ? "bg-green-500" : valor >= meta - 10 ? "bg-orange-400" : "bg-red-500";
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />;
}

export default function DashboardGerencia() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [supervisorSeleccionado, setSupervisorSeleccionado] = useState(null);
  const [busqueda, setBusqueda] = useState("");

  const cargar = () => {
    setError("");
    fetchDashboardGerencia()
      .then(setData)
      .catch(() => setError("No se pudo cargar el dashboard de Gerencia."));
  };

  useEffect(() => { cargar(); }, []);

  const ejecutivosVisibles = useMemo(() => {
    if (!data?.ejecutivos) return [];
    const q = busqueda.trim().toLowerCase();
    return data.ejecutivos.filter((e) => {
      const pertenece = !supervisorSeleccionado || e.ejecutivo.supervisor_id === supervisorSeleccionado;
      const coincide = !q || [e.ejecutivo.nombre, e.ejecutivo.rut, e.ejecutivo.equipo, e.ejecutivo.supervisor_nombre]
        .some((v) => String(v || "").toLowerCase().includes(q));
      return pertenece && coincide;
    });
  }, [data, supervisorSeleccionado, busqueda]);

  const riesgoEjecutivos = useMemo(() => [...(data?.ejecutivos || [])]
    .sort((a, b) => a.promedio_focos - b.promedio_focos)
    .slice(0, 8), [data]);

  const totalAccionable = useMemo(() => {
    const a = data?.accionables || {};
    return (a.hoy?.rgu || 0) + (a.manana?.rgu || 0) + (a.prox_3d?.rgu || 0);
  }, [data]);

  return (
    <Layout
      titulo="Dashboard Gerencia"
      items={[
        { label: "Dashboard", to: "/dashboard" },
        { label: "Ejecutivos", to: "/ejecutivos" },
        { label: "Accionables", to: "/accionables" },
        { label: "Cobranza", to: "/cobranza" },
        { label: "Apelaciones", to: "/apelaciones" },
        { label: "Base de Datos", to: "/base-datos" },
        { label: "Histórico", to: "/historico" },
        { label: "Análisis", to: "/analisis" },
        { label: "Cargar Datos", to: "/cargar-datos" },
        { label: "Auditoría KPI", to: "/auditoria-kpi" },
        { label: "Permisos", to: "/permisos" },
        { label: "Admin", href: ADMIN_URL },
      ]}
    >
      {error && <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {!error && !data && <div className="h-72 rounded-2xl bg-gray-100 animate-pulse" />}

      {data && (
        <div className="space-y-5 pb-8">
          <section className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Última medición oficial Claro</p>
                <h2 className="mt-1 text-xl font-bold text-gray-900 sm:text-2xl">
                  {data.snapshot_actual?.dia_reporte || "Sin reporte"} · corte {data.snapshot_actual?.fecha_corte || "—"}
                </h2>
                <p className="mt-1 text-sm text-gray-500 break-all">{data.snapshot_actual?.archivo_nombre || "Aún no hay KPI cargado"}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {["B1", "B2", "B3"].map((b) => (
                  <div key={b} className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-xs">
                    <strong className="text-gray-800">{b}</strong>{" "}
                    <span className="text-gray-500">{nombreMes(data.snapshot_actual?.focos?.[b])}</span>{" "}
                    <span className="text-gray-400">· Meta {data.snapshot_actual?.metas?.[b] ?? "—"}%</span>
                  </div>
                ))}
                <button onClick={cargar} className="min-h-10 rounded-xl bg-gray-900 px-4 text-xs font-semibold text-white hover:bg-black">
                  ↻ Actualizar
                </button>
              </div>
            </div>
          </section>

          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ["Clientes ESACOM", data.operacion?.clientes, "text-gray-900"],
              ["Instaladas", data.operacion?.instaladas, "text-green-700"],
              ["Pend. instalación", data.operacion?.pendiente_instalacion, "text-orange-600"],
              ["Pend. comercial", data.operacion?.pendiente_comercial, "text-blue-700"],
              ["Ejecutivos activos", data.operacion?.ejecutivos_regulares_activos, "text-gray-900"],
              ["Supervisores", data.operacion?.supervisores_activos, "text-gray-900"],
              ["RGU accionables 0–3d", totalAccionable, "text-red-700"],
              ["Ventas anuladas", data.operacion?.anuladas, "text-gray-500"],
            ].map(([label, value, color]) => (
              <div key={label} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] uppercase tracking-wide text-gray-400">{label}</p>
                <p className={`mt-1 text-2xl font-bold sm:text-3xl ${color}`}>{Number(value || 0).toLocaleString("es-CL")}</p>
              </div>
            ))}
          </section>

          <section>
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-gray-900">KPI global vigente</h2>
                <p className="text-xs text-gray-500">Misma regla validada en Ejecutivo y Supervisor: venta y RGU desde ESACOM; Claro aporta estado KPI.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              {(data.global || []).map((c) => <KpiCard key={`${c.boleta}-${c.mes_ano}`} corte={c} />)}
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-gray-100 p-4 sm:p-5">
                <h2 className="font-bold text-gray-900">Evolución último snapshot</h2>
                <p className="mt-1 text-xs text-gray-500">
                  Compara la misma camada/boleta del KPI actual contra el reporte anterior. No mezcla focos distintos.
                </p>
              </div>
              <div className="divide-y divide-gray-100">
                {(data.comparacion || []).map((c) => (
                  <div key={c.boleta} className="p-4 sm:p-5 flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{c.boleta} · {nombreMes(c.mes_ano)}</p>
                      <p className="text-xs text-gray-400">{BOLETA_NOMBRE[c.boleta]}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-bold text-gray-900">{c.actual ? porcentaje(c.actual.pct_cumplimiento) : "—"}</p>
                      {c.anterior ? (
                        <p className={`text-xs font-semibold ${c.delta_pp >= 0 ? "text-green-700" : "text-red-700"}`}>
                          {c.delta_pp >= 0 ? "+" : ""}{c.delta_pp.toFixed(1)} pp vs anterior ({porcentaje(c.anterior.pct_cumplimiento)})
                        </p>
                      ) : <p className="text-xs text-gray-400">Sin base comparable anterior</p>}
                    </div>
                  </div>
                ))}
              </div>
              {data.snapshot_anterior && (
                <div className="bg-gray-50 px-4 py-3 text-[11px] text-gray-500">
                  Reporte anterior: {data.snapshot_anterior.archivo_nombre} · corte {data.snapshot_anterior.fecha_corte}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-gray-100 p-4 sm:p-5">
                <h2 className="font-bold text-gray-900">Auditoría del último KPI</h2>
                <p className="mt-1 text-xs text-gray-500">Diferencias se mantienen para revisión; no reemplazan datos maestros ESACOM.</p>
              </div>
              <div className="grid grid-cols-2 gap-3 p-4 sm:p-5">
                {[
                  ["Cruces", data.auditoria?.cruzados, "text-green-700"],
                  ["Sin venta ESACOM", data.auditoria?.sin_cruce, "text-orange-600"],
                  ["Inconsistencias", data.auditoria?.inconsistencias, "text-red-700"],
                  ["RUT", data.auditoria?.diferencia_rut, "text-gray-900"],
                  ["RGU", data.auditoria?.diferencia_rgu, "text-gray-900"],
                  ["Propietario Claro", data.auditoria?.diferencia_propietario, "text-gray-900"],
                  ["Estado", data.auditoria?.diferencia_estado, "text-gray-900"],
                  ["Fuera medición", data.auditoria?.fuera_medicion, "text-gray-500"],
                ].map(([label, value, color]) => (
                  <div key={label} className="rounded-xl bg-gray-50 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-gray-400">{label}</p>
                    <p className={`mt-1 text-xl font-bold ${color}`}>{Number(value || 0).toLocaleString("es-CL")}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-gray-100 p-4 sm:p-5">
              <h2 className="font-bold text-gray-900">Ranking por Supervisor</h2>
              <p className="mt-1 text-xs text-gray-500">Ordenado desde el equipo con menor promedio de focos. Pulsa un equipo para bajar a sus ejecutivos.</p>
            </div>
            <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
              {(data.supervisores || []).map((s) => {
                const activo = supervisorSeleccionado === s.supervisor.id;
                return (
                  <button
                    key={s.supervisor.id}
                    onClick={() => setSupervisorSeleccionado(activo ? null : s.supervisor.id)}
                    className={`rounded-2xl border p-4 text-left transition ${activo ? "border-gray-900 ring-2 ring-gray-900/10" : "border-gray-200 hover:border-gray-400"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-gray-900">{s.supervisor.nombre}</p>
                        <p className="text-xs text-gray-400">{s.supervisor.equipo || "Sin equipo"} · {s.ejecutivos} ejecutivos</p>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{porcentaje(s.promedio_focos)}</p>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      {s.cortes.map((c) => (
                        <div key={c.boleta} className="rounded-lg bg-gray-50 p-2 text-center">
                          <p className="text-[10px] text-gray-400">{c.boleta}</p>
                          <p className="text-sm font-bold">{porcentaje(c.pct_cumplimiento)}</p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-xs text-gray-500">Q meta total <strong className="text-gray-900">{s.q_para_meta_total} RGU</strong></p>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-gray-100 p-4 sm:p-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="font-bold text-gray-900">Drill-down de Ejecutivos</h2>
                <p className="mt-1 text-xs text-gray-500">
                  {supervisorSeleccionado ? "Mostrando solo el equipo seleccionado." : "Todos los ejecutivos regulares medidos."}
                </p>
              </div>
              <div className="flex gap-2">
                <input
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  placeholder="Buscar nombre, RUT, equipo..."
                  className="min-h-10 w-full rounded-xl border border-gray-300 px-3 text-sm lg:w-72"
                />
                {supervisorSeleccionado && <button onClick={() => setSupervisorSeleccionado(null)} className="rounded-xl border px-3 text-xs">Todos</button>}
              </div>
            </div>
            <div className="hidden lg:block overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-400">
                  <tr>
                    <th className="px-4 py-3 text-left">Ejecutivo</th>
                    <th className="px-4 py-3 text-left">Supervisor</th>
                    <th className="px-4 py-3 text-center">B1</th>
                    <th className="px-4 py-3 text-center">B2</th>
                    <th className="px-4 py-3 text-center">B3</th>
                    <th className="px-4 py-3 text-right">Promedio</th>
                    <th className="px-4 py-3 text-right">Q meta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ejecutivosVisibles.map((e) => {
                    const qMeta = e.cortes.reduce((s, c) => s + (c.faltan_para_meta || 0), 0);
                    return (
                      <tr key={e.ejecutivo.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3"><p className="font-semibold">{e.ejecutivo.nombre}</p><p className="text-xs text-gray-400">{e.ejecutivo.rut}</p></td>
                        <td className="px-4 py-3 text-gray-500">{e.ejecutivo.supervisor_nombre || "—"}</td>
                        {["B1", "B2", "B3"].map((b) => {
                          const c = e.cortes.find((x) => x.boleta === b);
                          return <td key={b} className="px-4 py-3 text-center font-semibold">{c ? porcentaje(c.pct_cumplimiento) : "—"}</td>;
                        })}
                        <td className="px-4 py-3 text-right"><Semaforo valor={e.promedio_focos} meta={82} /> <strong className="ml-1">{porcentaje(e.promedio_focos)}</strong></td>
                        <td className="px-4 py-3 text-right font-semibold">{qMeta}</td>
                      </tr>
                    );
                  })}
                  {!ejecutivosVisibles.length && <tr><td colSpan="7" className="p-8 text-center text-gray-400">No hay ejecutivos para este filtro.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="grid gap-3 p-3 lg:hidden">
              {ejecutivosVisibles.map((e) => {
                const qMeta = e.cortes.reduce((s, c) => s + (c.faltan_para_meta || 0), 0);
                return (
                  <div key={e.ejecutivo.id} className="rounded-xl border border-gray-200 p-4">
                    <div className="flex justify-between gap-3">
                      <div><p className="font-semibold text-gray-900">{e.ejecutivo.nombre}</p><p className="text-xs text-gray-400">{e.ejecutivo.supervisor_nombre || "—"} · {e.ejecutivo.rut}</p></div>
                      <p className="text-xl font-bold">{porcentaje(e.promedio_focos)}</p>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      {e.cortes.map((c) => <div key={c.boleta} className="rounded-lg bg-gray-50 p-2 text-center"><p className="text-[10px] text-gray-400">{c.boleta}</p><p className="font-bold">{porcentaje(c.pct_cumplimiento)}</p></div>)}
                    </div>
                    <p className="mt-3 text-xs text-gray-500">Q para meta total: <strong>{qMeta} RGU</strong></p>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm">
              <h2 className="font-bold text-gray-900">Ejecutivos con mayor riesgo</h2>
              <div className="mt-3 space-y-2">
                {riesgoEjecutivos.map((e, idx) => (
                  <div key={e.ejecutivo.id} className="flex items-center gap-3 rounded-xl bg-gray-50 p-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white border text-xs font-bold text-gray-500">{idx + 1}</div>
                    <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{e.ejecutivo.nombre}</p><p className="truncate text-xs text-gray-400">{e.ejecutivo.supervisor_nombre || "Sin supervisor"}</p></div>
                    <p className="text-lg font-bold text-red-700">{porcentaje(e.promedio_focos)}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm">
              <h2 className="font-bold text-gray-900">Gestión inmediata</h2>
              <div className="mt-3 grid grid-cols-3 gap-3">
                {[
                  ["Hoy", data.accionables?.hoy],
                  ["Mañana", data.accionables?.manana],
                  ["Próx. 3 días", data.accionables?.prox_3d],
                ].map(([label, item]) => (
                  <div key={label} className="rounded-xl bg-gray-50 p-3 text-center">
                    <p className="text-[10px] uppercase text-gray-400">{label}</p>
                    <p className="mt-1 text-2xl font-bold text-gray-900">{item?.rgu || 0}</p>
                    <p className="text-[11px] text-gray-500">RGU · {item?.clientes || 0} clientes</p>
                  </div>
                ))}
              </div>
              <a href="/accionables" className="mt-4 block min-h-11 rounded-xl bg-gray-900 px-4 py-3 text-center text-sm font-semibold text-white">Abrir Accionables</a>
            </div>
          </section>
        </div>
      )}
    </Layout>
  );
}
