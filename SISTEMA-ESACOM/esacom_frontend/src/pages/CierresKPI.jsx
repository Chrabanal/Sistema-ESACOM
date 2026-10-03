import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { ADMIN_URL } from "../api/client";
import {
  descargarCierreKpiCsv,
  fetchCierreKpiGerenciaDetalle,
  fetchCierresKpiGerencia,
} from "../api/dashboard";

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function nombreMes(valor) {
  if (!valor || !String(valor).includes("-")) return valor || "—";
  const [anio, mes] = String(valor).split("-");
  return `${MESES[Number(mes) - 1]} ${anio}`;
}

function numero(valor) {
  return Number(valor || 0).toLocaleString("es-CL");
}

function porcentaje(valor) {
  return valor == null ? "—" : `${Number(valor).toFixed(2)}%`;
}

function fechaCorta(valor) {
  if (!valor) return "—";
  const p = String(valor).split("-");
  return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : valor;
}

function TarjetaDato({ label, value, tone = "dark", detail }) {
  const tonos = {
    green: "text-green-700",
    blue: "text-blue-700",
    red: "text-red-700",
    orange: "text-orange-600",
    dark: "text-gray-900",
  };
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-black ${tonos[tone]}`}>{value}</p>
      {detail && <p className="mt-1 text-[11px] text-gray-400">{detail}</p>}
    </div>
  );
}

function TablaDesglose({ filas, tipo }) {
  if (!filas?.length) {
    return <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-8 text-center text-sm text-gray-400">Sin datos para este cierre.</div>;
  }
  const tienePlanilla = filas.some((fila) => fila.planilla_cierre);
  return (
    <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full min-w-[1120px] text-sm">
        <thead className="border-b border-gray-200 bg-gray-50 text-[10px] uppercase tracking-wide text-gray-400">
          <tr>
            <th className="px-4 py-3 text-left">{tipo === "ejecutivos" ? "Ejecutivo" : "Supervisor"}</th>
            {tipo === "ejecutivos" && <th className="px-4 py-3 text-left">Supervisor</th>}
            <th className="px-4 py-3 text-right">No pago</th>
            <th className="px-4 py-3 text-right">Fuera plazo</th>
            <th className="px-4 py-3 text-right">Pago</th>
            <th className="px-4 py-3 text-right">Pendiente</th>
            <th className="px-4 py-3 text-right">S/B</th>
            {tienePlanilla && <th className="px-4 py-3 text-right">#N/D</th>}
            {tienePlanilla && <th className="px-4 py-3 text-right">Total cierre</th>}
            {tienePlanilla && <th className="px-4 py-3 text-right">KPI cierre</th>}
            <th className="px-4 py-3 text-right">KPI CRM</th>
            <th className="px-4 py-3 text-right">Q meta</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {filas.map((fila, idx) => (
            <tr key={`${fila.id || fila.rut || fila.nombre}-${idx}`} className="hover:bg-gray-50/60">
              <td className="px-4 py-3">
                <p className="font-semibold text-gray-800">{fila.nombre || "—"}</p>
                {tipo === "ejecutivos" && <p className="mt-0.5 text-[11px] text-gray-400">{fila.rut || ""}</p>}
              </td>
              {tipo === "ejecutivos" && <td className="px-4 py-3 text-gray-500">{fila.supervisor || "Sin supervisor"}</td>}
              <td className="px-4 py-3 text-right font-bold text-red-700">{numero(fila.no_pago)}</td>
              <td className="px-4 py-3 text-right font-bold text-orange-600">{numero(fila.fuera_plazo)}</td>
              <td className="px-4 py-3 text-right font-bold text-green-700">{numero(fila.pagadas)}</td>
              <td className="px-4 py-3 text-right font-bold text-blue-700">{numero(fila.pendientes)}</td>
              <td className="px-4 py-3 text-right text-gray-500">{numero(fila.sin_boleta)}</td>
              {tienePlanilla && <td className="px-4 py-3 text-right text-gray-500">{numero(fila.planilla_cierre?.n_d)}</td>}
              {tienePlanilla && <td className="px-4 py-3 text-right font-semibold text-gray-800">{numero(fila.planilla_cierre?.total_general)}</td>}
              {tienePlanilla && <td className="px-4 py-3 text-right font-black text-purple-700">{porcentaje(fila.planilla_cierre?.kpi_pct)}</td>}
              <td className="px-4 py-3 text-right font-black text-gray-900">{porcentaje(fila.pct_cumplimiento)}</td>
              <td className="px-4 py-3 text-right font-semibold text-gray-700">{fila.faltan_para_meta == null ? "—" : numero(fila.faltan_para_meta)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CierresKPI() {
  const [canal, setCanal] = useState("FIJO");
  const [data, setData] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [mes, setMes] = useState("");
  const [vista, setVista] = useState("consolidado");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [descargando, setDescargando] = useState("");

  useEffect(() => {
    let activo = true;
    setError("");
    setData(null);
    setDetalle(null);
    setMes("");
    fetchCierresKpiGerencia(canal)
      .then((resp) => {
        if (!activo) return;
        setData(resp);
        const primero = resp.cierres?.[0]?.mes_ano || "";
        setMes(primero);
      })
      .catch(() => activo && setError("No se pudieron cargar los cierres KPI."));
    return () => { activo = false; };
  }, [canal]);

  useEffect(() => {
    if (!mes) {
      setDetalle(null);
      return undefined;
    }
    let activo = true;
    setCargando(true);
    setDetalle(null);
    fetchCierreKpiGerenciaDetalle(canal, mes)
      .then((resp) => activo && setDetalle(resp))
      .catch(() => activo && setError("No se pudo abrir el cierre seleccionado."))
      .finally(() => activo && setCargando(false));
    return () => { activo = false; };
  }, [canal, mes]);

  const actual = data?.actual;
  const cierres = data?.cierres || [];
  const cierreSeleccionado = detalle?.cierre;
  const resumen = detalle?.resumen || {};
  const planillaCierre = detalle?.planilla_cierre || null;
  const cumple = Number(resumen.meta_pct || 0) > 0 && Number(resumen.pct_cumplimiento || 0) >= Number(resumen.meta_pct || 0);

  async function descargar(tipo) {
    if (!mes) return;
    const llave = `${tipo}-${mes}`;
    setDescargando(llave);
    try {
      await descargarCierreKpiCsv(canal, mes, tipo);
    } finally {
      setDescargando("");
    }
  }

  return (
    <Layout
      titulo="Cierres KPI"
      items={[
        { label: "Dashboard", to: "/dashboard" },
        { label: "Ejecutivos", to: "/ejecutivos" },
        { label: "Cierres KPI", to: "/cierres-kpi" },
        { label: "Accionables", to: "/accionables" },
        { label: "Histórico", to: "/historico" },
        { label: "Análisis", to: "/analisis" },
        { label: "Auditoría KPI", to: "/auditoria-kpi" },
        { label: "Admin", href: ADMIN_URL },
      ]}
    >
      <div className="space-y-6 pb-8">
        <section className="rounded-2xl border border-blue-100 bg-blue-50/50 p-4 sm:p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-bold text-gray-900">El cierre lo determina Claro</p>
              <p className="mt-1 max-w-3xl text-sm text-gray-600">Un período solo se congela cuando se carga un <strong>CIERRE oficial</strong>. Los AVANCE pueden seguir cambiando y nunca cierran el mes de forma manual.</p>
            </div>
            <div className="inline-flex w-fit rounded-xl border border-gray-200 bg-white p-1 shadow-sm">
              {[
                ["FIJO", "Fijo"],
                ["MOVIL", "Móvil"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => { setCanal(value); setVista("consolidado"); }}
                  className={`min-h-10 rounded-lg px-5 text-sm font-bold transition ${canal === value ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-50"}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </section>

        {error && <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        {!data && !error && <div className="h-48 animate-pulse rounded-2xl bg-gray-100" />}

        {data && (
          <>
            <section>
              <div className="mb-3 border-l-4 border-lime-500 pl-3">
                <h2 className="text-lg font-bold text-gray-900">Período vigente · {canal === "FIJO" ? "Fijo" : "Móvil"}</h2>
                <p className="text-xs text-gray-500">Último AVANCE recibido; permanece abierto hasta que Claro envíe su CIERRE.</p>
              </div>
              {actual ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-sm">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-xl font-black text-gray-900">{nombreMes(actual.mes_ano)} · {actual.boleta}</h3>
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-black text-amber-800">EN CURSO</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Corte {fechaCorta(actual.fecha_corte)} · {actual.archivo || "Reporte Claro"}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
                      <div><p className="text-[10px] uppercase text-gray-400">KPI actual</p><p className="font-black text-gray-900">{porcentaje(actual.resumen?.pct_cumplimiento)}</p></div>
                      <div><p className="text-[10px] uppercase text-gray-400">Meta</p><p className="font-black text-gray-900">{porcentaje(actual.resumen?.meta_pct ?? actual.meta_pct)}</p></div>
                      <div><p className="text-[10px] uppercase text-gray-400">Referencia Claro</p><p className="font-black text-blue-700">{porcentaje(actual.referencia_claro)}</p></div>
                      <div><p className="text-[10px] uppercase text-gray-400">Q meta</p><p className="font-black text-gray-900">{numero(actual.resumen?.faltan_para_meta)}</p></div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-6 text-sm text-gray-500">No existe un AVANCE abierto para este canal.</div>
              )}
            </section>

            <section>
              <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div className="border-l-4 border-lime-500 pl-3">
                  <h2 className="text-lg font-bold text-gray-900">Histórico de cierres oficiales</h2>
                  <p className="text-xs text-gray-500">Cada período proviene del primer CIERRE oficial recibido y queda congelado.</p>
                </div>
                {cierres.length > 0 && (
                  <label className="text-xs font-semibold text-gray-500">
                    Período
                    <select value={mes} onChange={(e) => { setMes(e.target.value); setVista("consolidado"); }} className="ml-2 min-h-10 rounded-xl border border-gray-200 bg-white px-3 text-sm font-semibold text-gray-800 outline-none focus:border-lime-400">
                      {cierres.map((c) => <option key={c.mes_ano} value={c.mes_ano}>{nombreMes(c.mes_ano)} · {c.boleta}</option>)}
                    </select>
                  </label>
                )}
              </div>

              {cierres.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-8 text-center text-sm text-gray-400">Todavía no hay cierres oficiales para este canal.</div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {cierres.map((c) => (
                    <button key={c.mes_ano} type="button" onClick={() => { setMes(c.mes_ano); setVista("consolidado"); }} className={`rounded-2xl border p-4 text-left shadow-sm transition ${mes === c.mes_ano ? "border-lime-400 bg-lime-50/40 ring-1 ring-lime-300" : "border-gray-200 bg-white hover:border-gray-300"}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-black text-gray-900">{nombreMes(c.mes_ano)}</p>
                        <span className="rounded-full bg-green-50 px-2 py-1 text-[10px] font-black text-green-700">CIERRE OFICIAL</span>
                      </div>
                      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                        <div><p className="text-gray-400">KPI</p><p className="mt-1 font-black text-gray-900">{porcentaje(c.resumen?.pct_cumplimiento)}</p></div>
                        <div><p className="text-gray-400">Meta</p><p className="mt-1 font-bold text-gray-700">{porcentaje(c.resumen?.meta_pct ?? c.meta_pct)}</p></div>
                        <div><p className="text-gray-400">Claro</p><p className="mt-1 font-bold text-blue-700">{porcentaje(c.referencia_claro)}</p></div>
                      </div>
                      <p className="mt-3 truncate text-[11px] text-gray-400">{fechaCorta(c.fecha_corte)} · {c.archivo}</p>
                    </button>
                  ))}
                </div>
              )}
            </section>

            {mes && (
              <section>
                {cargando && (
                  <div className="flex h-40 items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50 text-sm font-semibold text-gray-500">
                    Cargando detalle del cierre…
                  </div>
                )}
                {!cargando && detalle && (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-xl font-black text-gray-900">Cierre {nombreMes(cierreSeleccionado?.mes_ano)}</h2>
                            <span className="rounded-full bg-green-50 px-2.5 py-1 text-[10px] font-black text-green-700">CIERRE OFICIAL {canal}</span>
                          </div>
                          <p className="mt-1 text-xs text-gray-500">{cierreSeleccionado?.archivo} · corte {fechaCorta(cierreSeleccionado?.fecha_corte)} · {cierreSeleccionado?.boleta}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button type="button" onClick={() => descargar("resumen")} disabled={!!descargando} className="min-h-10 rounded-xl border border-gray-200 bg-white px-4 text-xs font-bold text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                            {descargando === `resumen-${mes}` ? "Descargando..." : "↓ Resumen CSV"}
                          </button>
                          <button type="button" onClick={() => descargar("detalle")} disabled={!!descargando} className="min-h-10 rounded-xl bg-gray-900 px-4 text-xs font-bold text-white hover:bg-black disabled:opacity-50">
                            {descargando === `detalle-${mes}` ? "Descargando..." : "↓ Detalle CSV"}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
                      <TarjetaDato label="KPI CRM" value={porcentaje(resumen.pct_cumplimiento)} tone={cumple ? "green" : "red"} detail="Pago / RGU medibles" />
                      <TarjetaDato label="Meta" value={porcentaje(resumen.meta_pct ?? cierreSeleccionado?.meta_pct)} />
                      <TarjetaDato label="Pago" value={numero(resumen.pagadas)} tone="green" />
                      <TarjetaDato label="Pendiente" value={numero(resumen.pendientes)} tone="blue" />
                      <TarjetaDato label="No pago" value={numero(resumen.no_pago)} tone="red" />
                      <TarjetaDato label="Fuera plazo" value={numero(resumen.fuera_plazo)} tone="orange" />
                      <TarjetaDato label="Total medible" value={numero(resumen.total)} />
                      <TarjetaDato label="Q para meta" value={numero(resumen.faltan_para_meta)} />
                    </div>
                    {planillaCierre && (
                      <div className="rounded-2xl border border-purple-100 bg-purple-50/40 p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-sm font-bold text-gray-900">Control de cierre · formato planilla Gerencia</p>
                            <p className="mt-1 text-xs text-gray-500">Replica la tabla “Cierre KPI”: KPI = Pago / Total general, incluyendo S/B y #N/D. No reemplaza el KPI CRM.</p>
                          </div>
                          <div className="grid grid-cols-3 gap-5 text-right">
                            <div><p className="text-[10px] uppercase text-gray-400">#N/D</p><p className="font-black text-gray-900">{numero(planillaCierre.n_d)}</p></div>
                            <div><p className="text-[10px] uppercase text-gray-400">Total general</p><p className="font-black text-gray-900">{numero(planillaCierre.total_general)}</p></div>
                            <div><p className="text-[10px] uppercase text-gray-400">KPI cierre</p><p className="font-black text-purple-700">{porcentaje(planillaCierre.kpi_pct)}</p></div>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2 rounded-2xl border border-gray-200 bg-white p-2 shadow-sm">
                      {[
                        ["consolidado", "Consolidado"],
                        ["supervisores", "Supervisores"],
                        ["ejecutivos", "Ejecutivos"],
                      ].map(([value, label]) => (
                        <button key={value} type="button" onClick={() => setVista(value)} className={`min-h-10 rounded-xl px-4 text-sm font-bold ${vista === value ? "bg-lime-100 text-gray-900 ring-1 ring-lime-300" : "text-gray-500 hover:bg-gray-50"}`}>
                          {label}
                        </button>
                      ))}
                    </div>

                    {vista === "consolidado" && (
                      <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                          <h3 className="font-bold text-gray-900">Resultado congelado</h3>
                          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                            {[
                              ["Pago", resumen.pagadas],
                              ["Pendiente", resumen.pendientes],
                              ["No pago", resumen.no_pago],
                              ["Fuera plazo", resumen.fuera_plazo],
                              ["S/B", resumen.sin_boleta],
                              ["Fuera medición", resumen.fuera_medicion],
                            ].map(([label, value]) => (
                              <div key={label} className="rounded-xl bg-gray-50 p-3">
                                <p className="text-[10px] uppercase text-gray-400">{label}</p>
                                <p className="mt-1 text-xl font-black text-gray-900">{numero(value)}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                          <h3 className="font-bold text-gray-900">Trazabilidad Claro</h3>
                          <dl className="mt-4 space-y-3 text-sm">
                            <div className="flex justify-between gap-4"><dt className="text-gray-400">Estado</dt><dd className="font-bold text-green-700">Cierre oficial</dd></div>
                            <div className="flex justify-between gap-4"><dt className="text-gray-400">Canal</dt><dd className="font-bold text-gray-800">{canal}</dd></div>
                            <div className="flex justify-between gap-4"><dt className="text-gray-400">Referencia Claro</dt><dd className="font-bold text-blue-700">{porcentaje(cierreSeleccionado?.referencia_claro)}</dd></div>
                            <div className="flex justify-between gap-4"><dt className="text-gray-400">Fecha de corte</dt><dd className="font-bold text-gray-800">{fechaCorta(cierreSeleccionado?.fecha_corte)}</dd></div>
                            <div><dt className="text-gray-400">Archivo</dt><dd className="mt-1 break-all font-semibold text-gray-700">{cierreSeleccionado?.archivo}</dd></div>
                          </dl>
                        </div>
                      </div>
                    )}
                    {vista === "supervisores" && <TablaDesglose filas={detalle.supervisores} tipo="supervisores" />}
                    {vista === "ejecutivos" && <TablaDesglose filas={detalle.ejecutivos} tipo="ejecutivos" />}
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
