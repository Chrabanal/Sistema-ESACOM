import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORES_ESTADO = {
  Instaladas: "#178A46",
  "Pend. instalación": "#D97706",
  "Pend. comercial": "#7C3AED",
  Anuladas: "#6B7280",
};

const COLORES_URGENCIA = {
  Vencidos: "#D92D20",
  Hoy: "#E8710A",
  Mañana: "#D9A300",
  "Próx. 3 días": "#2563EB",
  "Vencido +8": "#D92D20",
  "Vencido 0-8": "#E8710A",
  "Vence 0-7": "#D9A300",
  "Vence +8": "#2563EB",
};

function TooltipSimple({ active, payload, label, sufijo = "" }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-gray-800">{label || payload?.[0]?.name || "Detalle"}</p>
      {payload.map((item) => (
        <p key={item.dataKey || item.name} className="mt-1 text-gray-500">
          {item.name}: <strong className="text-gray-900">{Number(item.value || 0).toLocaleString("es-CL")}{sufijo}</strong>
        </p>
      ))}
    </div>
  );
}

export function EstadoVentasDonut({ actividad, titulo = "Estado de ventas ESACOM" }) {
  const data = [
    { name: "Instaladas", value: Number(actividad?.instaladas || 0) },
    { name: "Pend. instalación", value: Number(actividad?.pendiente_instalacion || 0) },
    { name: "Pend. comercial", value: Number(actividad?.pendiente_comercial || 0) },
    { name: "Anuladas", value: Number(actividad?.anuladas || 0) },
  ];
  const total = data.reduce((acc, item) => acc + item.value, 0);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-extrabold text-gray-900">{titulo}</p>
          <p className="mt-1 text-[11px] text-gray-500">Distribución de las ventas del mes según ESACOM.</p>
        </div>
        <div className="text-right"><p className="text-2xl font-extrabold text-gray-900">{total}</p><p className="text-[10px] text-gray-400">ventas</p></div>
      </div>
      <div className="mt-3 grid grid-cols-1 items-center gap-3 sm:grid-cols-[160px_1fr]">
        <div className="h-36 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={40} outerRadius={62} paddingAngle={2}>
                {data.map((item) => <Cell key={item.name} fill={COLORES_ESTADO[item.name]} stroke="none" />)}
              </Pie>
              <Tooltip content={<TooltipSimple />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2 text-xs">
          {data.map((item) => (
            <div key={item.name} className="flex items-center justify-between gap-3">
              <span className="flex min-w-0 items-center gap-2 text-gray-500"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: COLORES_ESTADO[item.name] }} />{item.name}</span>
              <strong className="text-gray-900">{item.value}</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function UrgenciaBarChart({ items, titulo = "Prioridad de gestión", subtitulo = "RGU que requieren atención según vencimiento." }) {
  const data = (items || []).map((item) => ({
    name: item.name,
    value: Number(item.value || 0),
  }));
  const tieneDatos = data.some((item) => item.value > 0);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-extrabold text-gray-900">{titulo}</p>
      <p className="mt-1 text-[11px] text-gray-500">{subtitulo}</p>
      {tieneDatos ? (
        <div className="mt-3 h-52 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={false} tickLine={false} interval={0} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipSimple sufijo=" RGU" />} />
              <Bar dataKey="value" name="RGU" radius={[8, 8, 0, 0]}>
                {data.map((item) => <Cell key={item.name} fill={COLORES_URGENCIA[item.name] || "#2563EB"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-xs text-gray-400">Sin RGU pendientes en estos rangos.</div>}
    </div>
  );
}

export function MotivosPendienteBarChart({
  items = [],
  titulo = "Pendientes comerciales por motivo",
  subtitulo = "Casos que requieren gestión comercial.",
}) {
  const data = (items || []).map((item) => ({
    name: item.name,
    value: Number(item.value || 0),
  }));

  const tieneDatos = data.some((item) => item.value > 0);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-extrabold text-gray-900">{titulo}</p>
      <p className="mt-1 text-[11px] text-gray-500">{subtitulo}</p>

      {tieneDatos ? (
        <div className="mt-4 space-y-3">
          {data.map((item) => {
            const maximo = Math.max(...data.map((d) => d.value), 1);
            const ancho = Math.max((item.value / maximo) * 100, 8);

            return (
              <div key={item.name}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <span className="truncate text-[11px] font-semibold text-gray-700">
                    {item.name}
                  </span>
                  <span className="shrink-0 text-xs font-extrabold text-gray-900">
                    {item.value}
                  </span>
                </div>

                <div className="h-2.5 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-amber-400"
                    style={{ width: `${ancho}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-green-100 bg-green-50 p-4 text-center">
          <p className="text-xs font-bold text-green-700">
            ✓ No tienes pendientes comerciales este mes.
          </p>
        </div>
      )}
    </div>
  );
}

function nombreCorto(nombre = "") {
  const partes = String(nombre).trim().split(/\s+/).filter(Boolean);
  if (partes.length <= 2) return partes.join(" ");
  return `${partes[0]} ${partes[1]}`;
}

export function RankingKpiBarChart({ filas = [], obtenerCorte, limite = 8 }) {
  const tienePoblacion = (corte) => {
    if (!corte || corte.tiene_datos === false) return false;
    const total = Number(corte.total || 0);
    const categorias = [
      corte.pagadas,
      corte.pendientes,
      corte.no_pago,
      corte.fuera_plazo,
      corte.sin_boleta,
      corte.fuera_medicion,
    ].reduce((acc, valor) => acc + Number(valor || 0), 0);
    return total > 0 || categorias > 0;
  };

  const data = filas
    .map((fila) => {
      const corte = obtenerCorte(fila);
      return {
        name: nombreCorto(fila?.ejecutivo?.nombre || "Sin nombre"),
        kpi: Number(corte?.pct_cumplimiento || 0),
        meta: Number(corte?.meta_pct || 0),
        medido: tienePoblacion(corte),
      };
    })
    .filter((item) => item.meta > 0 && item.medido && item.kpi < item.meta)
    .sort((a, b) => a.kpi - b.kpi)
    .slice(0, limite);
  const meta = data[0]?.meta || 0;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-sm font-extrabold text-gray-900">Ejecutivos que requieren más apoyo</p>
        <p className="mt-1 text-[11px] text-gray-500">Solo considera ejecutivos con población KPI real y KPI bajo la meta. “Sin medición” y quienes ya cumplen quedan fuera del ranking.</p>
      </div>
      {data.length ? (
        <div className="mt-3 h-[330px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 20, left: 12, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E5E7EB" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" width={118} tick={{ fontSize: 10, fill: "#4B5563" }} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipSimple sufijo="%" />} />
              {meta > 0 && <ReferenceLine x={meta} stroke="#178A46" strokeDasharray="5 4" label={{ value: `Meta ${meta}%`, fill: "#178A46", fontSize: 10, position: "insideTopRight" }} />}
              <Bar dataKey="kpi" name="KPI" fill="#D92D20" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-xs text-gray-400">No hay ejecutivos medidos bajo la meta en este período.</div>}
    </div>
  );
}

export function TendenciaKpiChart({ corte }) {
  const anteriorRaw = corte?.kpi_anterior_pct;
  const actualRaw = corte?.pct_cumplimiento;

  const tieneAnterior = anteriorRaw !== null && anteriorRaw !== undefined;
  const tieneActual = actualRaw !== null && actualRaw !== undefined;

  const anterior = Number(anteriorRaw || 0);
  const actual = Number(actualRaw || 0);
  const meta = Number(corte?.meta_pct || 0);
  const faltan = Number(corte?.faltan_para_meta || 0);

  const variacionRaw = corte?.tendencia_pp;
  const variacion =
    variacionRaw !== null && variacionRaw !== undefined
      ? Number(variacionRaw)
      : actual - anterior;

  const fmt = (valor) =>
    Number(valor || 0).toLocaleString("es-CL", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const cumple = meta > 0 && actual >= meta;
  const subio = variacion > 0;
  const bajo = variacion < 0;

  let mensajeCambio = "Se mantiene igual";
  let simboloCambio = "→";

  if (subio) {
    mensajeCambio = `Subió ${fmt(Math.abs(variacion))} puntos`;
    simboloCambio = "↑";
  } else if (bajo) {
    mensajeCambio = `Bajó ${fmt(Math.abs(variacion))} puntos`;
    simboloCambio = "↓";
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-extrabold text-gray-900">
        Cómo vas con tu KPI
      </p>

      <p className="mt-1 text-[11px] text-gray-500">
        Compara tu KPI ESACOM anterior con tu resultado actual de esta misma medición.
      </p>

      {tieneAnterior && tieneActual ? (
        <>
          <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-center">
              <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400">
                Antes
              </p>
              <p className="mt-1 text-2xl font-black text-gray-700">
                {fmt(anterior)}%
              </p>
            </div>

            <div className="text-xl font-black text-gray-300">→</div>

            <div
              className={`rounded-xl border p-4 text-center ${
                cumple
                  ? "border-green-200 bg-green-50"
                  : "border-red-200 bg-red-50"
              }`}
            >
              <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400">
                Ahora
              </p>
              <p
                className={`mt-1 text-2xl font-black ${
                  cumple ? "text-green-700" : "text-red-700"
                }`}
              >
                {fmt(actual)}%
              </p>
            </div>
          </div>

          <div
            className={`mt-4 rounded-xl px-4 py-3 text-center ${
              subio
                ? "bg-green-50 text-green-700"
                : bajo
                  ? "bg-red-50 text-red-700"
                  : "bg-gray-50 text-gray-600"
            }`}
          >
            <p className="text-base font-black">
              {simboloCambio} {mensajeCambio}
            </p>
          </div>

          <div className="mt-4 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-center">
            <p className="text-[10px] font-bold uppercase tracking-wide text-green-700">
              Meta ESACOM
            </p>
            <p className="mt-1 text-xl font-black text-green-800">
              {fmt(meta)}%
            </p>
          </div>

          <div
            className={`mt-3 rounded-xl px-4 py-4 text-center ${
              cumple
                ? "bg-green-600 text-white"
                : "bg-orange-50 text-orange-800"
            }`}
          >
            {cumple ? (
              <>
                <p className="text-sm font-black">✓ Meta cumplida</p>
                <p className="mt-1 text-xs opacity-90">
                  Tu equipo ya alcanzó la meta de Calidad.
                </p>
              </>
            ) : (
              <>
                <p className="text-xs font-bold uppercase tracking-wide">
                  Necesitas
                </p>
                <p className="mt-1 text-2xl font-black">
                  {faltan} RGU más pagados
                </p>
                <p className="mt-1 text-xs">
                  para llegar al {fmt(meta)}%.
                </p>
              </>
            )}
          </div>
        </>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-xs text-gray-400">
          Cuando exista un reporte anterior comparable, aquí verás claramente cómo ibas y cómo vas ahora.
        </div>
      )}
    </div>
  );
}

