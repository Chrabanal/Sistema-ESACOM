import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

const NOMBRE_BOLETA = { B1: "1ª boleta", B2: "2ª boleta", B3: "3ª boleta" };

const COLOR_SEMAFORO = {
  verde: "border-esacom-green",
  amarillo: "border-esacom-orange",
  rojo: "border-esacom-red",
  sin_datos: "border-gray-200",
  informativo: "border-blue-300",
};
const COLOR_TEXTO_SEMAFORO = {
  verde: "text-esacom-green",
  amarillo: "text-esacom-orange",
  rojo: "text-esacom-red",
  sin_datos: "text-gray-500",
  informativo: "text-blue-700",
};
const COLORES_DONUT = {
  pagadas: "#1E8E3E",
  pendientes: "#2563EB",
  no_pago: "#DA291C",
  fuera_plazo: "#E8710A",
};

function nombreMes(mesAno = "") {
  const [anio, mes] = String(mesAno).split("-");
  const nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const i = Number(mes) - 1;
  return i >= 0 && i < 12 ? `${nombres[i]} ${anio}` : mesAno || "Sin mes";
}

function Tendencia({ valor }) {
  if (valor === null || valor === undefined) return <span className="text-gray-400">Sin reporte anterior comparable</span>;
  const n = Number(valor || 0);
  if (Math.abs(n) < 0.005) return <span className="text-gray-500">Sin cambio vs reporte anterior</span>;
  const sube = n > 0;
  return <span className={sube ? "font-semibold text-green-700" : "font-semibold text-red-700"}>{sube ? "↑" : "↓"} {Math.abs(n).toFixed(2)} pp vs reporte anterior</span>;
}

export default function KpiCard({ corte }) {
  const {
    mes_ano, boleta, pagadas = 0, pendientes = 0, no_pago = 0, fuera_plazo = 0, sin_boleta = 0,
    meta_pct = 0, pct_cumplimiento = 0, pct_proyectado = 0,
    faltan_para_meta = 0, semaforo = "sin_datos", unidad = "RGU", fuera_medicion = 0, gestion = {},
    tiene_datos, estado_medicion = "AVANCE", estado_mes = "EN_CURSO", valor_informado_claro = null, tendencia_pp = null,
    dia_reporte = "", fecha_corte = null, meta_definida = true, perfil_kpi = "REGULAR",
  } = corte;

  const sinDatos = tiene_datos === false || (!Number(corte.total || 0) && !Number(sin_boleta || 0) && !Number(fuera_medicion || 0));
  const datosDonut = [
    { key: "pagadas", value: pagadas },
    { key: "pendientes", value: pendientes },
    { key: "no_pago", value: no_pago },
    { key: "fuera_plazo", value: fuera_plazo },
  ];
  const totalDonut = datosDonut.reduce((acc, d) => acc + Number(d.value || 0), 0);
  const tieneMeta = meta_definida !== false && Number(meta_pct || 0) > 0;
  const avanceBarra = tieneMeta ? Math.min((Number(pct_cumplimiento || 0) / Number(meta_pct)) * 100, 100) : Math.min(Number(pct_cumplimiento || 0), 100);
  const cumple = !sinDatos && tieneMeta && Number(pct_cumplimiento || 0) >= Number(meta_pct || 0);
  const esHonorarios = perfil_kpi === "HONORARIOS" || meta_definida === false;
  const cerrado = estado_mes === "CERRADO" || estado_medicion === "CIERRE";

  return (
    <article className={`overflow-hidden rounded-2xl border border-l-4 border-gray-200 bg-white p-4 shadow-sm sm:p-5 ${COLOR_SEMAFORO[semaforo] || COLOR_SEMAFORO.sin_datos}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">{nombreMes(mes_ano)}</p>
            <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${cerrado ? "bg-green-50 text-green-700 ring-1 ring-green-200" : "bg-blue-50 text-blue-700 ring-1 ring-blue-100"}`}>{cerrado ? "CERRADO" : "EN CURSO"}</span>
          </div>
          <p className="mt-1 text-xs text-gray-400">Calidad de pago · referencia {NOMBRE_BOLETA[boleta] || boleta} · medición por RGU</p>
        </div>
        <div className="text-right">
          {sinDatos ? (
            <><p className="text-lg font-extrabold text-gray-500">Sin datos</p><p className="text-[11px] text-gray-400">Sin medición para tu cartera</p></>
          ) : (
            <>
              <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400">Tu KPI</p>
              <p className={`mt-1 text-3xl font-extrabold leading-none tracking-tight sm:text-4xl ${COLOR_TEXTO_SEMAFORO[semaforo] || "text-gray-700"}`}>{Number(pct_cumplimiento).toFixed(2)}%</p>
              <p className="mt-1 text-[11px] font-medium text-gray-600">{tieneMeta ? `Meta ESACOM ${Number(meta_pct).toFixed(1)}%` : "Meta Honorarios pendiente de definición"}</p>
            </>
          )}
        </div>
      </div>

      {!sinDatos && (
        <>
          {tieneMeta ? (
            <>
              <div className="mt-4 grid grid-cols-2 gap-2 sm:gap-3">
                <div className={`rounded-xl p-3 sm:p-4 ${cumple ? "bg-green-50" : "bg-red-50"}`}>
                  <p className="text-[10px] font-semibold uppercase text-gray-400">Resultado</p>
                  <p className={`text-lg font-extrabold sm:text-xl ${cumple ? "text-green-800" : "text-red-800"}`}>{cumple ? "✓ Cumples" : "Aún no cumples"}</p>
                  <p className="mt-1 text-[9px] text-gray-500">{cumple ? `Superas la meta por ${(Number(pct_cumplimiento) - Number(meta_pct)).toFixed(2)} pp.` : `Estás a ${(Number(meta_pct) - Number(pct_cumplimiento)).toFixed(2)} pp de la meta.`}</p>
                </div>
                <div className="rounded-xl bg-gray-50 p-3 sm:p-4">
                  <p className="text-[10px] font-semibold uppercase text-gray-400">Para llegar a la meta</p>
                  <p className="text-lg font-extrabold text-gray-900 sm:text-xl">{`${faltan_para_meta || 0} ${unidad}`}</p>
                  <p className="mt-1 text-[9px] text-gray-400">RGU que deben pasar a Pago.</p>
                </div>
              </div>

              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between text-[10px] text-gray-500">
                  <span>Avance hacia meta</span><span>{Number(pct_cumplimiento).toFixed(2)}% / {Number(meta_pct || 0).toFixed(0)}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                  <div className={`h-full transition-all ${cumple ? "bg-esacom-green" : semaforo === "amarillo" ? "bg-esacom-orange" : "bg-esacom-red"}`} style={{ width: `${avanceBarra}%` }} />
                </div>
              </div>
            </>
          ) : (
            <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/60 p-3 sm:p-4">
              <p className="text-[10px] font-semibold uppercase text-blue-600">Medición de Calidad</p>
              <p className="mt-1 text-lg font-extrabold text-blue-800 sm:text-xl">KPI de pago disponible</p>
              <p className="mt-1 text-[10px] text-blue-700/80">Se muestra tu porcentaje real de pago. La meta Honorarios aún no está definida, por lo que no se informa Cumple/No cumple ni Q para meta.</p>
            </div>
          )}

          <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/40 px-3 py-2 text-[10px] sm:text-[11px]">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-gray-700">Último reporte Claro</p>
                {(dia_reporte || fecha_corte) && <p className="mt-0.5 text-gray-400">{dia_reporte || "Reporte"}{fecha_corte ? ` · corte ${fecha_corte}` : ""}</p>}
              </div>
              <Tendencia valor={tendencia_pp} />
            </div>
            {valor_informado_claro !== null && valor_informado_claro !== undefined && (
              <p className="mt-1 text-gray-500">Referencia Claro ({cerrado ? "cierre" : "avance"}): <strong className="text-blue-700">{Number(valor_informado_claro).toFixed(2)}%</strong></p>
            )}
          </div>

          <div className="mt-4 flex items-center gap-3 sm:gap-4">
            <div className="h-16 w-16 shrink-0 sm:h-20 sm:w-20">
              {totalDonut > 0 ? (
                <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={datosDonut} dataKey="value" innerRadius={18} outerRadius={30} paddingAngle={2}>{datosDonut.map((d) => <Cell key={d.key} fill={COLORES_DONUT[d.key]} stroke="none" />)}</Pie></PieChart></ResponsiveContainer>
              ) : <div className="h-full w-full rounded-full border-4 border-gray-200" />}
            </div>
            <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-3 gap-y-1.5 text-xs sm:gap-x-4 sm:text-sm">
              <span className="text-gray-500">Pago</span><strong className="text-right text-green-700">{pagadas}</strong>
              <span className="text-gray-500">Pendiente</span><strong className="text-right text-blue-700">{pendientes}</strong>
              <span className="text-gray-500">No pago</span><strong className="text-right text-red-700">{no_pago}</strong>
              <span className="text-gray-500">Fuera plazo</span><strong className="text-right text-orange-700">{fuera_plazo}</strong>
            </div>
          </div>

          <div className="mt-4 border-t border-gray-100 pt-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-400">Qué debes gestionar</p>
            <div className="grid grid-cols-2 gap-2 text-[11px] sm:text-xs">
              <div className="rounded-lg bg-red-50 p-2"><span className="text-red-700">Vencido +8</span><strong className="float-right">{gestion.vencido_mas_8 || 0}</strong></div>
              <div className="rounded-lg bg-orange-50 p-2"><span className="text-orange-700">Vencido 0-8</span><strong className="float-right">{gestion.vencido_0_8 || 0}</strong></div>
              <div className="rounded-lg bg-yellow-50 p-2"><span className="text-yellow-700">Vence 0-7</span><strong className="float-right">{gestion.gestionar_0_7 || 0}</strong></div>
              <div className="rounded-lg bg-blue-50 p-2"><span className="text-blue-700">Vence +8</span><strong className="float-right">{gestion.gestionar_8_mas || 0}</strong></div>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-3 text-xs">
            {tieneMeta && pct_proyectado !== null && pct_proyectado !== undefined ? <span className="text-gray-500">Proyección según tasa actual: <strong className="text-esacom-blue">{Number(pct_proyectado).toFixed(2)}%</strong></span> : <span className="text-gray-500">{esHonorarios ? "KPI informativo sin meta Honorarios aplicada" : "Sin proyección disponible"}</span>}
            <span className="text-gray-400">S/B {sin_boleta} · Fuera medición {fuera_medicion}</span>
          </div>
        </>
      )}
    </article>
  );
}
