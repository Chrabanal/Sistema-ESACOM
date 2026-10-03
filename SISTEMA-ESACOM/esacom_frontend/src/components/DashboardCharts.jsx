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

function nombreCorto(nombre = "") {
  const partes = String(nombre).trim().split(/\s+/).filter(Boolean);
  if (partes.length <= 2) return partes.join(" ");
  return `${partes[0]} ${partes[1]}`;
}

export function RankingKpiBarChart({ filas = [], obtenerCorte, limite = 8 }) {
  const data = filas
    .map((fila) => {
      const corte = obtenerCorte(fila);
      return {
        name: nombreCorto(fila?.ejecutivo?.nombre || "Sin nombre"),
        kpi: Number(corte?.pct_cumplimiento || 0),
        meta: Number(corte?.meta_pct || 0),
      };
    })
    .filter((item) => item.meta > 0)
    .sort((a, b) => a.kpi - b.kpi)
    .slice(0, limite);
  const meta = data[0]?.meta || 0;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-sm font-extrabold text-gray-900">Ejecutivos que requieren más apoyo</p>
        <p className="mt-1 text-[11px] text-gray-500">Los KPI más bajos del período en curso. La línea indica la meta ESACOM.</p>
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
      ) : <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-xs text-gray-400">Aún no hay KPI comparable para graficar.</div>}
    </div>
  );
}

export function TendenciaKpiChart({ corte }) {
  const anterior = corte?.kpi_anterior_pct;
  const actual = corte?.pct_cumplimiento;
  const data = [];
  if (anterior !== null && anterior !== undefined) data.push({ name: "Reporte anterior", kpi: Number(anterior || 0) });
  if (actual !== null && actual !== undefined) data.push({ name: "Último reporte", kpi: Number(actual || 0) });
  const meta = Number(corte?.meta_pct || 0);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-extrabold text-gray-900">Tendencia de Calidad</p>
      <p className="mt-1 text-[11px] text-gray-500">Compara el último avance con el reporte anterior de la misma medición.</p>
      {data.length >= 2 ? (
        <div className="mt-3 h-52 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: -10, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipSimple sufijo="%" />} />
              {meta > 0 && <ReferenceLine y={meta} stroke="#178A46" strokeDasharray="5 4" />}
              <Line type="monotone" dataKey="kpi" name="KPI" stroke="#2563EB" strokeWidth={3} dot={{ r: 5, fill: "#2563EB" }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : <div className="mt-4 rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-xs text-gray-400">Cuando llegue el siguiente reporte comparable de Claro aparecerá aquí la evolución.</div>}
    </div>
  );
}
